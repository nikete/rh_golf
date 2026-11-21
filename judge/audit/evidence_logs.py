"""Save the verified checker transcripts in the public, content-addressed audit ledger."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile

from audit.checks import POLICY


def archive_checker_logs(receipt, source, destination):
    required = json.loads(POLICY.read_text())["required_checks"]
    results = receipt["checks"]
    if receipt.get("status") != "passed" or set(results) != set(required):
        raise ValueError("Incomplete checker evidence")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as tmp:
        staged = {}
        for checker in required:
            result = results[checker]
            if result["status"] != "passed" or result["exit_code"] != 0:
                raise ValueError(f"Checker {checker} did not pass")
            expected = result["log_sha256"]
            with (source / f"{checker}.log").open("rb") as raw:
                if expected in staged:
                    digest = hashlib.file_digest(raw, "sha256")
                else:
                    packed = Path(tmp) / f"{checker}.gz"
                    digest = hashlib.sha256()
                    with packed.open("wb") as out, gzip.GzipFile(
                            filename="", mode="wb", fileobj=out, mtime=0) as gz:
                        while chunk := raw.read(1 << 20):
                            digest.update(chunk)
                            gz.write(chunk)
                    staged[expected] = packed
                if digest.hexdigest() != expected:
                    raise ValueError(f"Checker transcript SHA-256 mismatch for {checker}")

        destination.mkdir(exist_ok=True)
        for digest, packed in staged.items():
            target = destination / f"{digest}.log.gz"
            if target.exists():
                with gzip.open(target, "rb") as archived:
                    if hashlib.file_digest(archived, "sha256").hexdigest() != digest:
                        raise ValueError(f"Corrupt archived checker transcript {digest}")
            else:
                packed.replace(target)
