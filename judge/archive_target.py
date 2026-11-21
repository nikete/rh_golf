"""Resolve and build a trusted module from the exact archived source revision."""
from pathlib import Path
import fcntl
import json
import os
import re
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MIRROR = "https://github.com/Deicyde/riemann-hypothesis.git"
REV = "40e56bab026552e089d7afcfeff08d2defb9c005"
MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z_][A-Za-z0-9_']*)*\Z")
HINT = "-- archive-module:"
IMPORT = "-- archive-import:"

class ArchiveTargetError(ValueError):
    """A bad or ambiguous entry target."""


class ArchiveBuildError(RuntimeError):
    """The trusted archive environment could not be prepared."""


def run(args, cwd, env, timeout, capture=False):
    try:
        with subprocess.Popen(args, cwd=cwd, env=env, text=True, start_new_session=True,
                              stdout=subprocess.PIPE if capture else None) as proc:
            try:
                out, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.communicate()
                raise
            if proc.returncode:
                raise subprocess.CalledProcessError(proc.returncode, args)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ArchiveBuildError(f"Archive preparation failed running {args[0]} {args[1]}: {exc}") from exc
    return out.strip() if capture else None


def find_module(src, target, source):
    line = source.splitlines()[0].strip() if source else ""
    if line.startswith(HINT):
        module = line.removeprefix(HINT).strip()
        if not MODULE.fullmatch(module) or not src.joinpath(*module.split(".")).with_suffix(".lean").is_file():
            raise ArchiveTargetError("Unknown archive module in -- archive-module: header")
        return module
    leaf = target.split(".")[-1]
    token = re.escape(leaf)
    # Module selection is a convenience. The trusted checker verifies the exact
    # declaration name, module of origin, universe arity, kind and type.
    pattern = rf"(?:theorem|lemma|def|abbrev|opaque)\s+(?:[\w'.«»]+\.)?{token}(?:\s|[:(\[{{]|$)"
    found = subprocess.run(["rg", "--files-with-matches", "--glob", "*.lean", "--", pattern, "."],
                           cwd=src, capture_output=True, text=True)
    if found.returncode not in (0, 1):
        raise ArchiveBuildError(f"Archive source search failed: {found.stderr[:300]}")
    files = found.stdout.splitlines()
    if len(files) > 1:
        exact = re.compile(r"(?:theorem|lemma|def|abbrev|opaque)\s+" + re.escape(target) + r"(?=\s|[:(\[{]|$)")
        qualified = [file for file in files if exact.search((src / file).read_text())]
        if len(qualified) == 1:
            files = qualified
    if len(files) != 1:
        raise ArchiveTargetError("Could not uniquely locate the declaration in source. Add "
                                 "-- archive-module: Qualified.Module as the first source line.")
    return ".".join(Path(files[0]).with_suffix("").parts)


def prepare_archive(target, source, env):
    with (ROOT / ".lake" / "rh-golf-archive.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _prepare(target, source, env)


def _prepare(target, source, env):
    # This environment is used only for trusted source/cache downloads and builds.
    network = {k: v for k, v in os.environ.items()
               if k.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy", "ssl_cert_file")}
    env = {**network, **env}
    checkout = ROOT / ".lake" / "rh-golf-archive"
    checkout.mkdir(exist_ok=True)
    if not (checkout / ".git").is_dir():
        run(["git", "init", "-q"], checkout, env, 30)
    current = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=checkout, capture_output=True, text=True)
    if current.stdout.strip() != REV:
        run(["git", "fetch", "-q", "--depth=1", MIRROR, REV], checkout, env, 600)
        run(["git", "checkout", "-q", "--detach", REV], checkout, env, 180)
    expected = {p["name"]: p["rev"] for p in json.loads((ROOT / "lake-manifest.json").read_text())["packages"]}
    pins = {p["name"]: p["rev"] for p in json.loads((checkout / "lake-manifest.json").read_text())["packages"]}
    if pins != expected:
        raise ArchiveBuildError("Archive dependency pins differ from the course pins")
    src = checkout / "src"
    module = find_module(src, target, source)
    modules = [module]
    for line in source.splitlines():
        line = line.strip()
        if not line or line.startswith(HINT):
            continue
        if not line.startswith(IMPORT):
            break
        extra = line.removeprefix(IMPORT).strip()
        if not MODULE.fullmatch(extra) or not src.joinpath(*extra.split(".")).with_suffix(".lean").is_file():
            raise ArchiveTargetError("Unknown pinned archive module in -- archive-import: header")
        if extra not in modules:
            modules.append(extra)
    # Every selected module must be a tracked file in this immutable checkout.
    tracked = ["src/" + m.replace(".", "/") + ".lean" for m in modules]
    run(["git", "ls-files", "--error-unmatch", "--", *tracked], checkout, env, 30, capture=True)
    run(["git", "diff", "--quiet", REV, "--", "src", "lakefile.toml", "lake-manifest.json"], checkout, env, 60)
    lake = checkout / ".lake"
    lake.mkdir(exist_ok=True)
    packages = lake / "packages"
    if not packages.exists():
        packages.symlink_to(ROOT / ".lake" / "packages", target_is_directory=True)
    build_env = {**env, "MATHLIB_CACHE_GET_URL": "https://cache.mathlib.org/mathlib4"}
    build_env.pop("LEAN_PATH", None)
    lib = lake / "build" / "lib" / "lean"
    if any(not lib.joinpath(*m.split(".")).with_suffix(".olean").exists() for m in modules):
        if not (packages / "mathlib/.lake/build/lib/lean/Mathlib.olean").exists():
            run(["lake", "exe", "cache", "get", "Mathlib"], ROOT, build_env, 900)
        run(["lake", "build", *["+" + m + ":olean" for m in modules]], checkout, build_env, 4 * 3600)
        # The public sandbox runs as nobody, and Mathlib cache files may be 0600.
        run(["chmod", "-R", "a+rX", str(ROOT / ".lake/packages"), str(lib)], ROOT, env, 300)
    return ",".join(modules), [str(lib)]
