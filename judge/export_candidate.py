"""Make challenge and solution exports for an accepted inert Lean certificate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile

from archive_graph import ArchiveGraph
from archive_target import prepare_archive
import run

EXPORTER_REVISION = "15f6055e299ad5b89345e533cc2192f4cc00f659"
MAX_EXPORT_BYTES = 8 << 30
TIMEOUT = 1800


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def limits(file_limit):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (file_limit, file_limit))


def export_candidate(target, source, certificate, receipt, solution, challenge,
                     file_limit=MAX_EXPORT_BYTES, timeout=TIMEOUT):
    if file_limit <= 0 or timeout <= 0:
        raise ValueError("Supply positive export and time limits")
    original = run.validate_source(source.read_text(encoding="utf-8"))
    record = json.loads(receipt.read_text())
    input_digest = hashlib.sha256(original.encode()).hexdigest()
    with certificate.open("rb") as stream:
        encoded = stream.read(run.MAX_CERT + 1)
    if (record.get("status") != "accepted" or record.get("hole") != target
            or record.get("source_sha256") != input_digest or record.get("verifier")
            or not 0 < len(encoded) <= run.MAX_CERT
            or record.get("certificate_sha256") != hashlib.sha256(encoded).hexdigest()):
        raise ValueError("The source, certificate and requested target must match the accepted Lean receipt")
    outputs = {solution.resolve(), challenge.resolve()}
    if len(outputs) != 2 or outputs.intersection(path.resolve() for path in (source, certificate, receipt)):
        raise ValueError("Choose separate output paths for the challenge and solution exports")
    _, body = run.directives(original)
    env, _ = run.clean_env()
    fast = run.FAST_NAMES.get(target, target)
    if fast not in run.TARGETS or (target in run.FAST_NAMES and
            body.lstrip().startswith(("-- archive-module:", "-- archive-import:"))):
        module, dirs = prepare_archive(target, body, env)
        if module != record.get("archive_module"):
            raise ValueError("Pinned archive module differs from its receipt")
        env["LEAN_PATH"] = os.pathsep.join([*map(str, dirs), env["LEAN_PATH"]])
        args = ["archive", module, json.dumps(ArchiveGraph.name_parts(target), ensure_ascii=False)]
    else:
        args = [run.TARGETS[fast]]
    solution.parent.mkdir(parents=True, exist_ok=True)
    challenge.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=solution.parent) as outdir, tempfile.TemporaryDirectory(dir=challenge.parent) as refdir:
        new = Path(outdir).resolve() / "solution.ndjson"
        reference = Path(refdir).resolve() / "challenge.ndjson"
        inert = new.parent / "proof.json"
        inert.write_bytes(encoded)
        cmd = ["lean", "--run", str(run.ROOT / "judge/Replay.lean"), "--export", str(new), str(reference),
               *args, str(inert)]
        result = subprocess.run(cmd, cwd=run.ROOT, env=env, check=True, text=True, stdout=subprocess.PIPE,
                                timeout=timeout, preexec_fn=lambda: limits(file_limit))
        replay = json.loads(result.stdout)
        for field in ("nodes", "helpers", "axioms", "impact", "archive_deps"):
            if replay.get(field) != record.get(field):
                raise ValueError(f"Replay disagrees with the accepted receipt on {field}")
        subject = replay["export_subject"]
        whole = target in ("riemannHypothesis", "riemann")
        if whole and subject != ["riemannHypothesis"]:
            raise ValueError("Ordinary-RH export has the wrong root declaration")
        if not new.stat().st_size or not reference.stat().st_size:
            raise ValueError("The trusted exporter did not produce both streams")
        result = {"scope": "whole-rh" if whole else "declaration", "subject": subject,
                  "target": target, "source_sha256": input_digest,
                  "certificate_sha256": record["certificate_sha256"], "exporter_revision": EXPORTER_REVISION,
                  "solution_sha256": digest(new), "challenge_sha256": digest(reference)}
        os.replace(new, solution)
        os.replace(reference, challenge)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True)
    for flag in ("--source", "--certificate", "--receipt", "--output", "--challenge"):
        parser.add_argument(flag, type=Path, required=True)
    parser.add_argument("--max-export-bytes", type=int, default=MAX_EXPORT_BYTES)
    parser.add_argument("--timeout-seconds", type=int, default=TIMEOUT)
    args = parser.parse_args()
    try:
        result = export_candidate(args.target, args.source, args.certificate, args.receipt, args.output, args.challenge,
                                  args.max_export_bytes, args.timeout_seconds)
    except (ValueError, run.Rejected, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(f"Could not materialize candidate: {exc}")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
