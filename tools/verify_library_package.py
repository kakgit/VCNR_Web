"""Exercise the library package ingest path against an in-memory R2 stand-in.

Scratch harness (not shipped): verifies _store_library_content_package()
rejects a bad Library Converter selection and stores a good one, and that the
HLS builder targets the best quality instead of an arbitrary chunk.
"""
import asyncio
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import routes  # noqa: E402
from backend.core import hls as hls_lib  # noqa: E402
from fastapi import HTTPException, UploadFile  # noqa: E402

STORE: dict = {}
MOVE_ID = "dc"
MOVIE = {"id": MOVE_ID, "title": "DC"}


def _put(key, body):
    STORE[key] = bytes(body)


def _del(key):
    STORE.pop(key, None)


def _list(prefix):
    return sorted(k for k in STORE if k.startswith(prefix))


def patch_storage():
    routes.upload_media_object = lambda key, body, content_type=None: _put(key, body)
    routes.upload_media_object_stream = lambda key, fileobj, content_type=None: _put(key, fileobj.read())
    routes.delete_media_object = _del
    routes.list_media_keys = _list
    routes.media_object_exists = lambda key: key in STORE
    routes.delete_media_prefix = lambda prefix: [STORE.pop(k) for k in _list(prefix)]
    routes.r2_enabled = lambda: True
    routes._write_content_manifest = lambda movie_id, manifest: None


def _upload(path, payload):
    upload = UploadFile(filename=Path(path).name, file=io.BytesIO(payload))
    upload._test_path = path
    return upload


def build_package(payloads, drop=None, omit_manifest=False, package_kind="library"):
    """UploadFiles mirroring Library Converter's content/ folder layout.

    ``drop`` removes files from the *selection only*; the manifest still
    references them. That is the realistic "half-copied folder" case.
    """
    drop = drop or set()
    files = []
    if not omit_manifest:
        by_quality = {}
        for name in payloads:
            by_quality.setdefault("720p" if "-720p-" in name else "480p", []).append(name)
        qualities = []
        for quality in sorted(by_quality):
            records = [
                {
                    "name": name, "quality_code": quality, "quality_label": quality.upper(),
                    "media_kind": "video", "chunk_index": index,
                    "chunk_size": len(payloads[name]), "source_size": len(payloads[name]),
                    "sha256": hashlib.sha256(payloads[name]).hexdigest(),
                    "md5": hashlib.md5(payloads[name]).hexdigest(),
                    "source_extension": ".mp4",
                }
                for index, name in enumerate(sorted(by_quality[quality]), start=1)
            ]
            qualities.append({
                "quality_code": quality, "quality_label": quality.upper(), "stars_required": 0,
                "sort_order": 1 if quality == "480p" else 2, "source_name": f"dc-{quality}.mkv",
                "source_extension": ".mp4", "uploaded_at": "2026-01-01T00:00:00Z",
                "chunk_count": len(records), "files": records, "subtitle_files": [],
            })
        files.append(_upload("content/manifest.json", json.dumps({
            "movie_id": MOVE_ID, "movie_title": "DC", "package_kind": package_kind,
            "qualities": qualities, "files": [], "subtitle_files": [], "encryption": {},
            "chunk_count": 0, "total_bytes": 0,
        }).encode()))
    for name, payload in payloads.items():
        if name in drop:
            continue
        quality = "720p" if "-720p-" in name else "480p"
        files.append(_upload(f"content/{quality}/dc-{quality}.library-pkg/{name}", payload))
    return files


def paths_of(files):
    return [getattr(f, "_test_path", f.filename) for f in files]


def expect_error(label, files, needle, results):
    try:
        asyncio.run(routes._store_library_content_package(MOVIE, files, paths_of(files)))
    except HTTPException as error:
        ok = needle in str(error.detail)
        print(f"  {'PASS' if ok else 'FAIL'} {label}: {error.detail}")
        results.append(ok)
        return
    print(f"  FAIL {label}: expected rejection, got success")
    results.append(False)


def main():
    patch_storage()
    payloads = {"dc-480p-1.mp4": b"A" * 32, "dc-480p-2.mp4": b"B" * 16, "dc-720p-1.mp4": b"C" * 64}
    results = []

    print("Library package ingest:")
    no_manifest = [f for f in build_package(payloads) if f.filename != "manifest.json"]
    expect_error("missing manifest.json", no_manifest, "manifest.json", results)
    # The manifest lists dc-720p-1.mp4 but the operator only selected 3 of 4 files.
    expect_error("missing referenced chunk", build_package(payloads, drop={"dc-720p-1.mp4"}),
                 "Missing chunk file for 720P: dc-720p-1.mp4", results)
    expect_error("encrypted vcnr package", build_package(payloads, package_kind="vcnr"),
                 "Library Converter package", results)
    expect_error("empty selection", [], "select the converted content folder", results)

    STORE.clear()
    good = build_package(payloads)
    manifest, count = asyncio.run(routes._store_library_content_package(MOVIE, good, paths_of(good)))
    stored = sorted(k for k in STORE if k.endswith(".mp4"))
    ok = (manifest.get("package_kind") == "library" and count == 3
          and manifest.get("encryption") == {} and len(stored) == 3
          and all(STORE[k] == payloads[Path(k).name] for k in stored))
    print(f"  {'PASS' if ok else 'FAIL'} valid package stored {count} chunks as {len(stored)} objects")
    if not ok:
        print(f"        package_kind={manifest.get('package_kind')} stored={stored}")
    results.append(ok)

    STORE.clear()
    partial = build_package(payloads, drop={"dc-720p-1.mp4"})
    try:
        asyncio.run(routes._store_library_content_package(MOVIE, partial, paths_of(partial)))
    except HTTPException:
        pass
    ok = not [k for k in STORE if k.endswith(".mp4")]
    print(f"  {'PASS' if ok else 'FAIL'} rejected package wrote no objects (atomicity)")
    results.append(ok)

    keys = hls_lib._library_package_chunk_keys(manifest)
    ok = keys == [f"{MOVE_ID}/content/720p/dc-720p.library-pkg/dc-720p-1.mp4"]
    print(f"  {'PASS' if ok else 'FAIL'} HLS targets the best quality, not a random chunk: {keys}")
    results.append(ok)

    ok = hls_lib._library_package_chunk_keys({}) == []
    print(f"  {'PASS' if ok else 'FAIL'} HLS falls back for a non-library manifest")
    results.append(ok)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

