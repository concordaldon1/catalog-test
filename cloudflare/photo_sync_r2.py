"""Upload Google Drive catalog photos to R2 through the authenticated Pages Function."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloudflare_publish import get_public, load_config, publish_manifest, upload_photo  # noqa: E402

CONFIG_FILE = Path(__file__).with_name("photo_sync_config.json")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
STATE_FILE = Path(__file__).with_name("photo_sync_r2_state.json")


def load_photo_source() -> Path:
    if not CONFIG_FILE.is_file():
        raise RuntimeError(f"Could not find {CONFIG_FILE}. Keep it beside this script.")
    settings = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    source = Path(settings["source"]).expanduser()
    if not source.is_dir():
        raise RuntimeError(f"Google Drive photo folder was not found: {source}")
    return source


def content_type(path: Path) -> str:
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    base_url, _ = load_config()
    source = load_photo_source()
    images = sorted(
        (p for p in source.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS),
        key=lambda p: p.name.casefold(),
    )
    if not images:
        raise RuntimeError(f"No JPG, JPEG, PNG, or WebP files were found directly inside {source}.")

    print("ROLL INVENTORY - CLOUDFLARE PHOTO SYNC")
    print(f"Photo source: {source}")
    print(f"Catalog site: {base_url}")
    print(f"Files to publish: {len(images)}")
    answer = input("Upload/update these photos and refresh the manifest? (Y/N): ").strip().upper()
    if answer != "Y":
        print("Cancelled; nothing was uploaded.")
        return

    try:
        old_manifest = json.loads(get_public("/photos/manifest.json").decode("utf-8"))
        if not isinstance(old_manifest, list):
            old_manifest = []
    except Exception:
        old_manifest = []
    try:
        old_state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        old_state = {}

    new_state = {}
    uploaded = 0
    for number, path in enumerate(images, start=1):
        digest = file_hash(path)
        new_state[path.name] = digest
        if old_state.get(path.name) == digest and path.name in old_manifest:
            print(f"[{number}/{len(images)}] Unchanged {path.name}")
            continue
        upload_photo(path.name, path.read_bytes(), content_type(path))
        uploaded += 1
        print(f"[{number}/{len(images)}] Uploaded {path.name}")

    manifest = sorted(set(name for name in old_manifest if isinstance(name, str)) | {path.name for path in images}, key=str.casefold)
    publish_manifest(manifest)
    STATE_FILE.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
    print(f"\nSUCCESS: {uploaded} photo(s) uploaded; the manifest now lists {len(manifest)} photo(s).")
    print("Existing R2 photos are retained; this sync does not delete files.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled. Photos uploaded before cancellation remain available; the manifest was not refreshed.")
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        input("\nPress Enter to close...")
        raise SystemExit(1)
