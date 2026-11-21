import gzip
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "judge"))
from reuse import manifest


URL = "https://raw.githubusercontent.com/alice/a.repo/" + "1" * 40 + "/entries/v1.jsonl.gz"


class Response(BytesIO):
    status = 200

    def __init__(self, body, headers=None):
        super().__init__(body)
        self.headers = {} if headers is None else headers


class ManifestTests(unittest.TestCase):
    def read(self, packed, url=URL, sha=None, headers=None):
        digest = hashlib.sha256(packed).hexdigest() if sha is None else sha
        with patch.object(manifest, "build_opener") as transport:
            transport.return_value.open.return_value = Response(packed, headers)
            return list(manifest.fetch_pairs(url, digest))

    def test_names_and_byte_pin(self):
        rows = [["A.«x.y»", ["B", 1, "a.b"]], [["Unicode", "∞"], "D"]]
        data = "\r\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode()
        packed = gzip.compress(data)
        expected = [tuple(row) for row in rows]
        self.assertEqual(self.read(packed, sha=hashlib.sha256(packed).hexdigest().upper()), expected)
        for sha in (hashlib.sha256(data).hexdigest(), "a" * 63, ""):
            with self.subTest(sha=sha), self.assertRaisesRegex(ValueError, "SHA-256"):
                self.read(packed, sha=sha)

    def test_restrict_urls_before_io(self):
        self.assertEqual(manifest.validate_url(URL), URL)
        bad = [URL.replace("https:", "http:"), URL.replace("raw.", "rAw."),
               URL.replace("raw.", "name:secret@raw."), URL.replace(".com/", ".com:443/"),
               URL.replace(".com/", ".com.other/"), URL.replace("1" * 40, "main"),
               URL.replace("/entries/", "/%2e%2e/"), URL.replace("/entries/", "/../"),
               URL.replace("/entries/", "//"), URL.replace("/a.repo/", "/../"),
               URL + "?download=1", URL + "#anchor", URL + "\n", URL[:-3]]
        with patch.object(manifest, "build_opener") as transport:
            for url in bad:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    list(manifest.fetch_pairs(url, "0" * 64))
            transport.assert_not_called()

    def test_malformed_format(self):
        for value in (b"{}", b'["x"]', b"\n", b'["x",false]', b'["x",[true]]',
                      b'["x",[]]', b'["x",[-1]]', b'["x","A..b"]',
                      b'["x","\\ud800"]', b'["x","\xff"]', b"[[" * 1500):
            with self.subTest(value=value[:50]), self.assertRaisesRegex(ValueError, "line 1"):
                self.read(gzip.compress(value))
        for data in (b"", b"bad gzip", gzip.compress(b'["x","y"]')[:-5], gzip.compress(b"")):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.read(data)

    def test_bounds(self):
        data = b'["a","b"]\n'
        packed = gzip.compress(data * 2)
        for key, limit in (("MAX_COMPRESSED", len(packed) - 1), ("MAX_EXPANDED", len(data)),
                           ("MAX_PAIRS", 1), ("MAX_LINE", len(data) - 1)):
            with self.subTest(key=key), patch.object(manifest, key, limit), self.assertRaisesRegex(ValueError, "limit"):
                self.read(packed)
        with patch.object(manifest, "MAX_COMPRESSED", len(packed)):
            with self.assertRaisesRegex(ValueError, "compressed size"):
                self.read(packed, headers={"Content-Length": str(len(packed) + 1)})
            self.assertEqual(self.read(packed), [("a", "b"), ("a", "b")])

    def test_http_status_and_failures(self):
        for code, headers, etype in [(302, {}, ValueError), (404, {}, ValueError), (401, {}, ValueError),
                                     (429, {}, RuntimeError), (503, {}, RuntimeError),
                                     (403, {"X-RateLimit-Remaining": "0"}, RuntimeError)]:
            with self.subTest(code=code), patch.object(manifest, "build_opener") as transport:
                transport.return_value.open.side_effect = HTTPError(URL, code, "test", headers, BytesIO())
                with self.assertRaises(etype):
                    list(manifest.fetch_pairs(URL, "0" * 64))
                handler = transport.call_args.args[0]
                self.assertIsNone(handler.redirect_request(None, None, 302, "", {}, URL))
        with patch.object(manifest, "build_opener") as transport:
            transport.return_value.open.side_effect = URLError("offline")
            with self.assertRaisesRegex(RuntimeError, "download failed"):
                list(manifest.fetch_pairs(URL, "0" * 64))
        with self.assertRaisesRegex(RuntimeError, "advertised length"):
            self.read(b"small", headers={"Content-Length": "30"})


if __name__ == "__main__":
    unittest.main()
