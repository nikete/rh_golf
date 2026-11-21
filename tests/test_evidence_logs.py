import gzip
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from audit.evidence_logs import archive_checker_logs


class EvidenceLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.source = Path(tmp.name) / "incoming"
        self.source.mkdir()
        self.dest = Path(tmp.name) / "audits/logs"
        self.receipt = {"status": "passed", "checks": {}}
        self.transcripts = {}
        for name in ("comparator", "lean_kernel", "nanoda", "con_leche", "con_leche_compare"):
            group = "comparator" if name in ("lean_kernel", "nanoda") else name
            data = (group + " transcript\n").encode()
            digest = hashlib.sha256(data).hexdigest()
            self.transcripts[digest] = data
            (self.source / (name + ".log")).write_bytes(data)
            self.receipt["checks"][name] = {"status": "passed", "exit_code": 0, "log_sha256": digest}

    def test_verified_logs_are_deduplicated_and_reproducible(self):
        archive_checker_logs(self.receipt, self.source, self.dest)
        archive_checker_logs(self.receipt, self.source, self.dest)
        second = self.dest.with_name("repeat")
        archive_checker_logs(self.receipt, self.source, second)
        self.assertEqual({p.name for p in self.dest.iterdir()}, {d + ".log.gz" for d in self.transcripts})
        for digest, data in self.transcripts.items():
            blob = self.dest / (digest + ".log.gz")
            self.assertEqual(gzip.decompress(blob.read_bytes()), data)
            self.assertEqual(blob.read_bytes(), (second / blob.name).read_bytes())
            self.assertEqual(blob.read_bytes()[4:8], bytes(4))

    def test_mismatch_in_shared_transcript_publishes_nothing(self):
        (self.source / "nanoda.log").write_bytes(b"different transcript")
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch for nanoda"):
            archive_checker_logs(self.receipt, self.source, self.dest)
        self.assertFalse(any(self.dest.glob("*.gz")))

    def test_corrupt_existing_blob_cannot_be_reused(self):
        archive_checker_logs(self.receipt, self.source, self.dest)
        blob = next(self.dest.iterdir())
        blob.write_bytes(gzip.compress(b"wrong bytes", mtime=0))
        with self.assertRaisesRegex(ValueError, "Corrupt archived checker transcript"):
            archive_checker_logs(self.receipt, self.source, self.dest)
