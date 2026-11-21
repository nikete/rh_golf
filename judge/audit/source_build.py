"""Build a complete ordinary-RH export with one accepted proof installed at its archive name."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "judge"))
import run
from archive_graph import ArchiveGraph
from archive_target import MIRROR, MODULE, REV

EXPORTER_SHA256 = "1c60d571dc24bfb99e7cbb218d8d489919bbc871238f6db9c76248521fbea998"
REFLECTION = "Formalism.VW.rh_of_right"
CTX = "structure Context where\n  env : Environment\n"
LOOKUP = "  let some declar := (← read).env.find? c\n"


def make_exporter(original, output):
    data = original.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPORTER_SHA256:
        raise ValueError("The exporter must match the pinned lean4export source")
    source = data.decode()
    if source.count(CTX) != 1 or source.count(LOOKUP) != 1:
        raise ValueError("Unsupported upstream exporter lookup")
    source = source.replace(CTX, CTX + "  replacement : Option ConstantInfo := none\n")
    source = source.replace(LOOKUP, """  let ctx ← read
  let override? := ctx.replacement.filter (fun d => d.name == c)
  let some declar := override?.orElse (fun _ => ctx.env.find? c)
""")
    output.write_text(source)


def inputs(target, source, certificate, receipt):
    record = json.loads(receipt.read_text())
    normalized = run.validate_source(source.read_text(encoding="utf-8"))
    if (record.get("status") != "accepted" or record.get("hole") != target or record.get("verifier")
            or record.get("source_sha256") != hashlib.sha256(normalized.encode()).hexdigest()
            or not 0 < certificate.stat().st_size <= run.MAX_CERT
            or record.get("certificate_sha256") != hashlib.sha256(certificate.read_bytes()).hexdigest()):
        raise ValueError("Expected the accepted Lean receipt and its exact source and certificate")
    modules = record.get("archive_module", "").split(",") if record.get("archive_module") else []
    if not all(MODULE.fullmatch(m) for m in modules):
        raise ValueError("Invalid resolved archive module on receipt")
    if target == "reflection":
        target = REFLECTION
    if not modules and target != REFLECTION:
        raise ValueError("Expected a named archive replacement or the legacy reflection entry")
    return target, modules


def build_archive(work, modules, env):
    archive = work / "archive"
    archive.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=archive, env=env, check=True)
    subprocess.run(["git", "fetch", "-q", "--depth=1", "--no-tags", MIRROR, REV],
                   cwd=archive, env=env, check=True, timeout=900)
    subprocess.run(["git", "checkout", "-q", "--detach", "FETCH_HEAD"], cwd=archive, env=env, check=True)
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=archive, env=env, text=True).strip() != REV:
        raise ValueError("Wrong original archive revision")

    def pins(folder):
        packages = json.loads((folder / "lake-manifest.json").read_text())["packages"]
        return {p["name"]: p["rev"] for p in packages}

    if pins(archive) != pins(ROOT):
        raise ValueError("Rebuilt archive and judge have different dependency revisions")
    lake = archive / ".lake"
    lake.mkdir(exist_ok=True)
    (lake / "packages").symlink_to(ROOT / ".lake/packages", target_is_directory=True)
    planned = list(dict.fromkeys(["Main", *modules]))
    for module in planned:
        if not (archive / "src").joinpath(*module.split(".")).with_suffix(".lean").is_file():
            raise ValueError(f"Missing pinned source for {module}")
    clean = {k: v for k, v in env.items() if k != "LEAN_PATH"}
    clean["LAKE_ARTIFACT_CACHE"] = "false"
    clean["MATHLIB_CACHE_GET_URL"] = "https://cache.mathlib.org/mathlib4"
    if not (lake / "packages/mathlib/.lake/build/lib/lean/Mathlib.olean").is_file():
        subprocess.run(["lake", "exe", "cache", "get", "Mathlib"], cwd=ROOT, env=clean, check=True)
    subprocess.run(["lake", "build", *["+" + m + ":olean" for m in planned]], cwd=archive, env=clean, check=True)
    return lake / "build/lib/lean"


def materialize(target, source, certificate, receipt, output):
    target, modules = inputs(target, source, certificate, receipt)
    if output.exists():
        raise ValueError("Choose a new output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    env, _ = run.clean_env()
    network = {k: v for k, v in os.environ.items() if k.lower() in
               {"http_proxy", "https_proxy", "all_proxy", "no_proxy", "ssl_cert_file"}}
    with tempfile.TemporaryDirectory(prefix=".source-build-", dir=output.parent) as temporary:
        work = Path(temporary).resolve()
        lib = build_archive(work, modules, {**network, **env})
        patched = work / "SourceOverlayExport.lean"
        make_exporter(ROOT / ".lake/rh-golf-exporter/Export.lean", patched)
        env["LEAN_PATH"] = os.pathsep.join([str(work), str(lib), env["LEAN_PATH"]])
        subprocess.run(["lean", "-o", "SourceOverlayExport.olean", patched.name], cwd=work, env=env, check=True)
        result = work / "solution.ndjson"
        name = json.dumps(ArchiveGraph.name_parts(target), ensure_ascii=False)
        subprocess.run(["lean", "--run", str(HERE / "SourceBuild.lean"), ",".join(modules), name,
                        str(certificate.resolve()), str(result)], cwd=work, env=env, check=True)
        if not result.stat().st_size:
            raise ValueError("Empty whole-solution export")
        os.replace(result, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    for name in ("source", "certificate", "receipt", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    materialize(args.target, args.source, args.certificate, args.receipt, args.output)
