"""Private desktop publisher for the catalog's Cloudflare Pages Function."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def config_path() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return root / "ConcordAldon" / "cloudflare.json"


def load_config() -> tuple[str, str]:
    path = config_path()
    if not path.is_file():
        raise RuntimeError(
            f"Cloudflare publishing is not configured. Create {path} using the setup instructions."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        base_url = data["pages_url"].strip().rstrip("/")
        token = data["upload_token"].strip()
    except Exception as exc:
        raise RuntimeError(f"Could not read Cloudflare settings at {path}: {exc}") from exc
    if not base_url.startswith("https://") or not token:
        raise RuntimeError("Cloudflare settings must contain an https Pages URL and upload token.")
    return base_url, token


def request(method: str, route: str, body: bytes, content_type: str) -> bytes:
    base_url, token = load_config()
    req = Request(
        base_url + route,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": content_type,
            "User-Agent": "Concord-Aldon-Catalog-Publisher/1.0",
        },
    )
    try:
        with urlopen(req, timeout=90) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Cloudflare returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Cloudflare: {exc.reason}") from exc


def get_public(route: str) -> bytes:
    base_url, _ = load_config()
    try:
        with urlopen(base_url + route, timeout=60) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Could not read live catalog (HTTP {exc.code}): {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach Cloudflare: {exc.reason}") from exc


def publish_inventory(inventory_text: str, timestamp_text: str) -> dict:
    body = json.dumps({"inventory": inventory_text, "timestamp": timestamp_text}).encode("utf-8")
    result = request("PUT", "/admin/inventory", body, "application/json; charset=utf-8")
    try:
        return json.loads(result.decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("Cloudflare returned an unreadable inventory publish response.") from exc


def upload_photo(filename: str, content: bytes, content_type: str) -> None:
    from urllib.parse import quote

    route = "/admin/photos/" + quote(filename, safe="")
    request("PUT", route, content, content_type)


def publish_manifest(filenames: list[str]) -> None:
    body = (json.dumps(filenames, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    request("PUT", "/admin/manifest", body, "application/json; charset=utf-8")
