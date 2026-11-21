"""Reparse the actual candidate export and measure its ordinary RH closure."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile

from rewrite import export_stream, hash_file
BASELINE = Path(__file__).resolve().parents[1] / "baseline"
sys.path.insert(0, str(BASELINE))
from catalog import catalog


def measure_export(source, library, work, expected):
    if not library.is_file():
        raise ValueError("Missing inventory from the pinned Mathlib environment")
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work, prefix="recount-") as folder:
        stage = Path(folder)
        # Freeze the exact inventory whose digest is included in the audit.
        staged_library = stage / "mathlib-names.jsonl.gz"
        shutil.copyfile(library, staged_library)
        for tool in ("index", "measure"):
            subprocess.run(["c++", "-O3", "-std=c++20", str(BASELINE / (tool + ".cpp")),
                            "-o", str(stage / tool)], check=True)
        digest = hashlib.sha256()
        with export_stream(source) as data:
            with subprocess.Popen([stage / "index", stage], stdin=subprocess.PIPE) as indexer:
                try:
                    while chunk := data.read(4 << 20):
                        digest.update(chunk)
                        indexer.stdin.write(chunk)
                finally:
                    indexer.stdin.close()
                if indexer.wait():
                    raise ValueError("Raw candidate export indexing failed")
        root = "riemannHypothesis"
        catalog(stage, roots=(root,))
        groups = json.loads((stage / "targets.json").read_text())
        measured = json.loads(subprocess.check_output([stage / "measure", stage, "--root-only", str(groups[root])]))
        if expected != measured["nodes"]:
            raise ValueError(f"Candidate has {measured['nodes']} RH nodes; supplied score expects {expected}")
        return {**measured, "export_sha256": digest.hexdigest(), "root": root,
                "mathlib_inventory_sha256": hash_file(staged_library)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--mathlib-names", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True, help="Temporary storage for compact expression indices")
    parser.add_argument("--expected", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in (args.input.resolve(), args.mathlib_names.resolve()):
        parser.error("The output receipt must have its own path")
    result = measure_export(args.input, args.mathlib_names, args.work, args.expected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=args.output.parent, delete=False) as f:
        json.dump(result, f, sort_keys=True)
        f.write("\n")
    os.replace(f.name, args.output)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
