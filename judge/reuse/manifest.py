"""Read checksum-pinned public GitHub manifests of exact theorem substitutions."""
import gzip
import hashlib
import http.client
import io
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, Request
import zlib

from archive_graph import ArchiveGraph


MAX_COMPRESSED = 32 << 20
MAX_EXPANDED = 160 << 20
MAX_PAIRS = 1_260_000
MAX_LINE = 64 << 10
PREFIX = "https://raw.githubusercontent.com/"


def validate_url(url, *, suffix=".jsonl.gz"):
    if not isinstance(url, str) or not url.startswith(PREFIX) or len(url) > 2048:
        raise ValueError("Use an HTTPS raw.githubusercontent.com URL pinned to a full commit SHA")
    parts = url[len(PREFIX):].split("/")
    if len(parts) < 4:
        raise ValueError(f"Expected an owner, repository, full commit SHA and {suffix} file path")
    owner, repo, commit, *path = parts
    if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", owner)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", repo) or repo in (".", "..")
            or not re.fullmatch(r"[A-Fa-f0-9]{40}", commit)
            or any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", item) or item in (".", "..") for item in path)
            or not path[-1].endswith(suffix)):
        raise ValueError(f"Invalid pinned GitHub URL or {suffix} file path")
    return url


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download(url):
    request = Request(url, headers={"User-Agent": "RH-Golf", "Accept-Encoding": "identity"})
    opener = build_opener(_NoRedirect())
    payload = io.BytesIO()
    deadline = time.monotonic() + 180
    try:
        with opener.open(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError(f"Unexpected GitHub manifest response (HTTP {response.status})")
            length = response.headers.get("Content-Length")
            if length is not None:
                if not re.fullmatch(r"[0-9]{1,20}", length):
                    raise RuntimeError("GitHub returned an invalid manifest content length")
                length = int(length)
                if length > MAX_COMPRESSED:
                    raise ValueError("Manifest exceeds the compressed size limit")
            while True:
                if time.monotonic() > deadline:
                    raise RuntimeError("GitHub manifest download timed out")
                chunk = response.read1(min(128 << 10, MAX_COMPRESSED - payload.tell() + 1))
                if not chunk:
                    break
                if payload.tell() + len(chunk) > MAX_COMPRESSED:
                    raise ValueError("Manifest exceeds the compressed size limit")
                payload.write(chunk)
            if length is not None and payload.tell() != length:
                raise RuntimeError("GitHub manifest download ended before the advertised length")
    except HTTPError as exc:
        with exc:
            code = exc.code
            if 300 <= code < 400:
                raise ValueError("Manifest URL redirects; use a direct pinned raw GitHub URL") from exc
            if code in (404, 410):
                raise ValueError(f"No public manifest at this pinned GitHub path (HTTP {code})") from exc
            if (code in (408, 425, 429) or code >= 500 or exc.headers.get("Retry-After")
                    or code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0"):
                raise RuntimeError(f"GitHub temporarily failed to serve the manifest (HTTP {code})") from exc
            raise ValueError(f"GitHub refused public access to this manifest (HTTP {code})") from exc
    except (URLError, http.client.HTTPException, OSError) as exc:
        raise RuntimeError(f"GitHub manifest download failed: {exc}") from exc
    return payload


def fetch_pairs(url, sha256):
    """Yield (target, donor) pairs in input order, preserving exact name representations."""
    validate_url(url)
    if not isinstance(sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", sha256):
        raise ValueError("Supply the full SHA-256 digest of the compressed manifest")
    payload = _download(url)
    yield from read_pairs(payload, sha256)


def read_pairs(payload, sha256):
    """Check the compressed bytes and parse the same pair grammar for local and remote files."""
    if hashlib.sha256(payload.getbuffer()).hexdigest() != sha256.lower():
        raise ValueError("Compressed manifest SHA-256 does not match the submitted digest")
    payload.seek(0)
    count = total = 0
    try:
        with gzip.GzipFile(fileobj=payload, mode="rb") as stream:
            while line := stream.readline(min(MAX_LINE, MAX_EXPANDED - total) + 1):
                count += 1
                total += len(line)
                if total > MAX_EXPANDED or len(line) > MAX_LINE or count > MAX_PAIRS:
                    raise ValueError("Manifest exceeds its expanded size, line length or pair count limit")
                try:
                    row = json.loads(line.decode("utf-8"))
                    if not isinstance(row, list) or len(row) != 2:
                        raise ValueError("expected a JSON array containing a target and donor")
                    for name in row:
                        for part in ArchiveGraph.name_parts(name):
                            if isinstance(part, str):
                                part.encode("utf-8")  # Reject unpaired surrogates in JSON escapes.
                except (ValueError, RecursionError) as exc:
                    raise ValueError(f"Invalid manifest pair on line {count}: {exc}") from exc
                yield row[0], row[1]
    except (gzip.BadGzipFile, EOFError, zlib.error) as exc:
        raise ValueError("Invalid or truncated gzip manifest") from exc
    if not count:
        raise ValueError("The manifest contains no substitution pairs")
