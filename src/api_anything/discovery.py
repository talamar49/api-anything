from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import yaml

from .models import SiteManifest


WRITE_HINTS = ("send", "submit", "delete", "create", "update", "post", "purchase", "pay", "message")


def normalize_site_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    if not value:
        raise ValueError("site_id cannot be empty")
    return value


def infer_capability_type(capability_id: str) -> str:
    lowered = capability_id.lower()
    if any(hint in lowered for hint in WRITE_HINTS):
        return "write"
    return "read"


def discover_site(
    root: str | Path,
    *,
    site_id: str,
    name: str,
    base_url: str,
    capabilities: Iterable[str] | None = None,
) -> SiteManifest:
    root = Path(root)
    site_id = normalize_site_id(site_id)
    site_dir = root / "sites" / site_id
    if site_dir.exists():
        raise FileExistsError(f"site already exists: {site_id}")

    site_dir.mkdir(parents=True)
    capability_ids = list(capabilities or ["read_page"])
    manifest_data = {
        "site_id": site_id,
        "name": name,
        "base_url": base_url,
        "auth": {"type": "unknown"},
        "capabilities": {},
    }
    for capability_id in capability_ids:
        capability_type = infer_capability_type(capability_id)
        manifest_data["capabilities"][capability_id] = {
            "type": capability_type,
            "params": {},
            "returns": "object",
        }
        if capability_type == "write":
            manifest_data["capabilities"][capability_id]["requires_confirmation"] = True

    (site_dir / "manifest.yaml").write_text(
        yaml.safe_dump(manifest_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (site_dir / "adapter.py").write_text(_adapter_stub(), encoding="utf-8")
    (site_dir / "docs.md").write_text(
        f"# {name}\n\nBase URL: {base_url}\n\nStatus: discovery skeleton.\n",
        encoding="utf-8",
    )
    return SiteManifest.model_validate(manifest_data)


def _adapter_stub() -> str:
    return '''def run(capability_id, params, context):
    """Generated API Anything adapter stub.

    Replace this with browser/CDP/API implementation after mapping the site.
    """
    return {
        "status": "stub",
        "capability_id": capability_id,
        "params": params,
        "site_id": context["site_id"],
    }
'''
