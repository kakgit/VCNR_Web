from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote


def bencode(value: Any) -> bytes:
    if isinstance(value, int):
        return b"i" + str(value).encode("ascii") + b"e"
    if isinstance(value, bytes):
        return str(len(value)).encode("ascii") + b":" + value
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return str(len(raw)).encode("ascii") + b":" + raw
    if isinstance(value, list):
        return b"l" + b"".join(bencode(item) for item in value) + b"e"
    if isinstance(value, dict):
        items: list[bytes] = []
        for key in sorted(value):
          key_bytes = key if isinstance(key, bytes) else str(key).encode("utf-8")
          items.append(bencode(key_bytes))
          items.append(bencode(value[key]))
        return b"d" + b"".join(items) + b"e"
    raise TypeError(f"Unsupported type for bencode: {type(value)!r}")


def build_piece_hashes(files: list[Path], piece_length: int) -> bytes:
    buffer = bytearray()
    hashes: list[bytes] = []

    for file_path in files:
        with file_path.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                buffer.extend(chunk)
                while len(buffer) >= piece_length:
                    piece = bytes(buffer[:piece_length])
                    hashes.append(hashlib.sha1(piece).digest())
                    del buffer[:piece_length]

    if buffer:
        hashes.append(hashlib.sha1(bytes(buffer)).digest())

    return b"".join(hashes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a public-style torrent file for VCNR encrypted chunks.")
    parser.add_argument("--content-dir", required=True, help="Directory containing the encrypted .vcnr files.")
    parser.add_argument("--output", required=True, help="Output .torrent path.")
    parser.add_argument("--name", required=True, help="Torrent package name.")
    parser.add_argument("--webseed", required=True, help="HTTP folder URL used as ws=/url-list fallback.")
    parser.add_argument("--piece-length", type=int, default=1024 * 1024, help="Piece length in bytes. Default: 1 MiB.")
    parser.add_argument("--comment", default="VCNR public trackerless swarm test package")
    parser.add_argument("--created-by", default="VCNR Codex Torrent Generator")
    args = parser.parse_args()

    content_dir = Path(args.content_dir).resolve()
    output_path = Path(args.output).resolve()
    files = sorted(path for path in content_dir.iterdir() if path.is_file() and path.suffix.lower() == ".vcnr")
    if not files:
        raise SystemExit(f"No .vcnr files found in {content_dir}")

    piece_hashes = build_piece_hashes(files, args.piece_length)
    info = {
        "name": args.name,
        "piece length": args.piece_length,
        "pieces": piece_hashes,
        "files": [
            {
                "length": file_path.stat().st_size,
                "path": [file_path.name],
            }
            for file_path in files
        ],
    }
    metainfo = {
        "comment": args.comment,
        "created by": args.created_by,
        "creation date": 1785580200,
        "url-list": [args.webseed],
        "info": info,
    }

    encoded = bencode(metainfo)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encoded)

    info_hash = hashlib.sha1(bencode(info)).hexdigest()
    summary = {
        "content_dir": str(content_dir),
        "output": str(output_path),
        "file_count": len(files),
        "piece_length": args.piece_length,
        "piece_count": len(piece_hashes) // 20,
        "info_hash_sha1": info_hash,
        "webseed": args.webseed,
        "magnet_uri": f"magnet:?xt=urn:btih:{info_hash}&dn={quote(args.name)}&ws={quote(args.webseed, safe=':/')}",
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
