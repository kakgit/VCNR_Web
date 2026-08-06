"""Verify a VCNR delivery .torrent against the bytes its webseed serves.

Use to debug downloads that stall at 0% when the swarm is webseed-only:

    python tools/verify_delivery_torrent.py r2-720p.torrent

Exit codes:
    0 = every piece hash matches the webseed content
    1 = piece hash mismatch (stale torrent or content re-uploaded)
    2 = webseed unreachable / unusable
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

FETCH_CHUNK = 1024 * 1024


def bdecode(data: bytes, pos: int = 0) -> tuple[object, int]:
    c = data[pos : pos + 1]
    if c == b"i":
        end = data.index(b"e", pos)
        return int(data[pos + 1 : end]), end + 1
    if c == b"l":
        pos += 1
        items: list[object] = []
        while data[pos : pos + 1] != b"e":
            item, pos = bdecode(data, pos)
            items.append(item)
        return items, pos + 1
    if c == b"d":
        pos += 1
        mapping: dict[bytes, object] = {}
        while data[pos : pos + 1] != b"e":
            key, pos = bdecode(data, pos)
            value, pos = bdecode(data, pos)
            mapping[key] = value
        return mapping, pos + 1
    if c.isdigit():
        end = data.index(b":", pos)
        length = int(data[pos:end])
        return data[end + 1 : end + 1 + length], end + 1 + length
    raise ValueError(f"Invalid bencode near offset {pos}")


def fetch_range(url: str, start: int, length: int) -> bytes | None:
    req = urllib.request.Request(
        url,
        headers={"Range": f"bytes={start}-{start + length - 1}", "User-Agent": "VCNR-torrent-verify/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if getattr(resp, "status", 200) not in (200, 206):
                return None
            return resp.read()
    except Exception:
        return None


def download_file(base: str, parts: list[bytes], size: int) -> bytes | None:
    rel = "/".join(p.decode("utf-8", "replace") for p in parts)
    url = base.rstrip("/") + "/" + urllib.request.quote(rel)
    buf = bytearray()
    for start in range(0, size, FETCH_CHUNK):
        take = min(FETCH_CHUNK, size - start)
        data = fetch_range(url, start, take)
        if data is None:
            return None
        buf.extend(data)
    return bytes(buf)


def piece_hashes(blob: bytes, piece_length: int) -> list[bytes]:
    return [hashlib.sha1(blob[o : o + piece_length]).digest() for o in range(0, len(blob), piece_length)]


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python tools/verify_delivery_torrent.py <file.torrent>")
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"torrent file not found: {path}")
        return 2

    root, _ = bdecode(path.read_bytes())
    info = root.get(b"info")
    if not isinstance(info, dict):
        print("Invalid torrent: missing info dict.")
        return 2

    piece_length = int(info.get(b"piece length", 0))
    pieces = info.get(b"pieces", b"")
    expected = len(pieces) // 20
    if b"files" in info:
        files = [(list(f[b"path"]), int(f[b"length"])) for f in info[b"files"]]
    else:
        files = [([info.get(b"name", b"")], int(info.get(b"length", 0)))]

    print(f"torrent name        : {info.get(b'name', b'').decode('utf-8', 'replace')}")
    print(f"piece length        : {piece_length} bytes")
    print(f"expected pieces     : {expected}")
    total = 0
    for parts, length in files:
        print(f"  file: {'/'.join(p.decode('utf-8', 'replace') for p in parts)}  {length} bytes")
        total += length
    print(f"total bytes         : {total}")

    webseeds = root.get(b"url-list", [])
    if not webseeds:
        print("No url-list (webseed) found in torrent - nothing to verify against.")
        return 2
    base = webseeds[0].decode("utf-8", "replace") if isinstance(webseeds[0], bytes) else str(webseeds[0])
    print(f"webseed base        : {base}")

    blob = bytearray()
    for parts, length in files:
        label = "/".join(p.decode("utf-8", "replace") for p in parts)
        print(f"downloading {label} ...")
        data = download_file(base, parts, length)
        if data is None:
            print(f"FAILED to download {label} from the webseed.")
            return 2
        blob.extend(data)

    actual = piece_hashes(bytes(blob), piece_length)
    print(f"downloaded size     : {len(blob)} bytes")
    print(f"computed pieces     : {len(actual)}")
    if len(actual) != expected:
        print(f"MISMATCH: piece counts differ (torrent={expected}, webseed={len(actual)}).")
        return 1

    expected_hashes = [pieces[j : j + 20] for j in range(0, len(pieces), 20)]
    bad = [i for i, (a, b) in enumerate(zip(actual, expected_hashes)) if a != b]
    if bad:
        print(f"PIECE HASH MISMATCH: {len(bad)}/{len(actual)} pieces differ (first: {bad[0]}).")
        print("The torrent metadata does not match the bytes the webseed serves.")
        return 1

    print("OK: every piece hash matches the webseed content - torrent and webseed are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
