"""Create the private local settings used by the inventory and photo publishers."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path


def main() -> None:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    config_path = root / "ConcordAldon" / "cloudflare.json"
    if config_path.exists():
        answer = input(f"Replace the existing settings at {config_path}? (Y/N): ").strip().upper()
        if answer != "Y":
            print("Cancelled; existing settings were kept.")
            return

    pages_url = input("Cloudflare Pages production URL (https://...): ").strip().rstrip("/")
    if not pages_url.startswith("https://"):
        raise ValueError("Enter the https:// address shown for the production Pages site.")
    token = secrets.token_urlsafe(48)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps({"pages_url": pages_url, "upload_token": token}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nLocal settings saved to: {config_path}")
    print("Copy this token into the Pages project's CATALOG_UPLOAD_TOKEN secret setting:")
    print(token)
    print("\nKeep this token private. Do not paste it into GitHub or the catalog page.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(1)
    except Exception as exc:
        print(f"\nERROR: {exc}")
        input("\nPress Enter to close...")
        raise SystemExit(1)
