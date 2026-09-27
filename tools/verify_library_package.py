"""Exercise the library package presign/register flow against an in-memory R2.

Scratch harness (not shipped). Mirrors the VCNR content-package flow: each
Library Converter chunk is presigned and PUT browser -> R2, then one manifest
registration finalises the title. Verifies key resolution, that a missing chunk
blocks registration, and that the HLS builder targets the best quality.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api import routes  # noqa: E402
from backend.core import hls as hls_lib  # noqa: E402
from fastapi import HTTPException  # noqa: E402

STORE: dict = {}
MOVE_ID = "dc"
MOVIE = {"id": MOVE_ID, "title": "DC"}


def patch_storage():
    def _put(key, body):
        STORE[key] = bytes(body)

    routes.upload_media_object = _put
    routes.upload_media_object_stream = lambda key, fileobj, content_type=None: _put(key, fileobj.read())
    routes.delete_media_object = lambda key: STORE.pop(key, None)
    routes.list_media_keys = lambda prefix: sorted(k for k in STORE if k.startswith(prefix))
    routes.media_object_exists = lambda key: key in STORE
    routes.delete_media_prefix = lambda prefix: [STORE.pop(k) for k in list(STORE) if k.startswith(prefix)]
    routes.r2_enabled = lambda: True
    routes._write_content_manifest = lambda movie_id, manifest: None


def quality_of(name):
    return "720p" if "-720p-" in name else "480p"


def build_manifest_json(payloads, package_kind="library"):
    """A Library Converter content/manifest.json describing every chunk."""
    by_quality = {}
    for name in payloads:
        by_quality.setdefault(quality_of(name), []).append(name)
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
    return json.dumps({
        "movie_id": MOVE_ID, "movie_title": "DC", "package_kind": package_kind,
        "qualities": qualities, "files": [], "subtitle_files": [], "encryption": {},
        "chunk_count": 0, "total_bytes": 0,
    })


def expect_http(label, call, needle, results):
    try:
        call()
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

    print("Presign: each chunk gets its own R2 key (browser -> R2, not via the API):")
    quality, filename, key = routes._library_content_destination(
        "dc", "content/480p/dc-480p.library-pkg/dc-480p-1.mp4")
    ok = (quality == "480p" and filename == "dc-480p-1.mp4"
          and key == "dc/content/480p/dc-480p.library-pkg/dc-480p-1.mp4")
    print(f"  {'PASS' if ok else 'FAIL'} chunk resolves into its own quality folder: {key}")
    results.append(ok)

    _, _, vtt_key = routes._library_content_destination(
        "dc", "content/720p/dc-720p.library-pkg/dc-720p-1SUB.vtt")
    ok = vtt_key.endswith("dc-720p-1SUB.vtt")
    print(f"  {'PASS' if ok else 'FAIL'} .vtt subtitle accepted: {vtt_key}")
    results.append(ok)

    expect_http("encrypted .vcnr chunk rejected",
                lambda: routes._library_content_destination("dc", "content/480p/p/dc-480p-1.vcnr"),
                ".mp4 chunks and .vtt subtitles", results)

    print("Register: manifest is finalised against what is really in storage:")
    STORE.clear()
    for name, payload in payloads.items():
        STORE[routes._library_chunk_key("dc", quality_of(name), name)] = payload
    manifest_json = build_manifest_json(payloads)
    manifest, count = routes._register_library_content_package(MOVIE, json.loads(manifest_json))
    ok = (manifest.get("package_kind") == "library" and count == 3
          and manifest.get("encryption") == {} and len(manifest["qualities"]) == 2)
    print(f"  {'PASS' if ok else 'FAIL'} register accepted {count} chunks across "
          f"{len(manifest['qualities'])} qualities")
    results.append(ok)

    STORE.pop(routes._library_chunk_key("dc", "720p", "dc-720p-1.mp4"))
    expect_http("missing chunk blocks registration",
                lambda: routes._register_library_content_package(MOVIE, json.loads(manifest_json)),
                "not found in storage", results)

    expect_http("encrypted vcnr package rejected",
                lambda: routes._register_library_content_package(
                    MOVIE, json.loads(build_manifest_json(payloads, package_kind="vcnr"))),
                "Library Converter package", results)

    # A quality listed with no chunk records must be refused.
    expect_http("quality with no chunk records rejected",
                lambda: routes._register_library_content_package(MOVIE, {
                    "package_kind": "library",
                    "qualities": [{"quality_code": "480p", "quality_label": "480P", "files": []}],
                }),
                "no chunk records in manifest.json", results)

    print("HLS build target:")
    keys = hls_lib._library_package_chunk_keys(manifest)
    ok = keys == ["dc/content/720p/dc-720p.library-pkg/dc-720p-1.mp4"]
    print(f"  {'PASS' if ok else 'FAIL'} picks the best quality, not a random chunk: {keys}")
    results.append(ok)

    ok = hls_lib._library_package_chunk_keys({}) == []
    print(f"  {'PASS' if ok else 'FAIL'} falls back for a non-library manifest")
    results.append(ok)

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
