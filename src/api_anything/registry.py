from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

from .hitl import require_human_approval
from .models import Capability, SiteManifest


class Registry:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.sites_dir = self.root / "sites"

    def list_sites(self) -> list[SiteManifest]:
        if not self.sites_dir.exists():
            return []
        manifests: list[SiteManifest] = []
        for manifest_path in sorted(self.sites_dir.glob("*/manifest.yaml")):
            manifests.append(SiteManifest.from_file(manifest_path))
        return manifests

    def get_site(self, site_id: str) -> SiteManifest:
        manifest_path = self.sites_dir / site_id / "manifest.yaml"
        if not manifest_path.exists():
            raise KeyError(f"site not found: {site_id}")
        manifest = SiteManifest.from_file(manifest_path)
        if manifest.site_id != site_id:
            raise ValueError(f"manifest site_id mismatch: expected {site_id}, got {manifest.site_id}")
        return manifest

    def get_capabilities(self, site_id: str) -> dict[str, Capability]:
        return self.get_site(site_id).capabilities

    def run_capability(
        self,
        site_id: str,
        capability_id: str,
        params: dict[str, Any],
        *,
        confirmed: bool = False,
        human_approval: dict[str, Any] | None = None,
    ) -> Any:
        manifest = self.get_site(site_id)
        capability = manifest.capabilities.get(capability_id)
        if capability is None:
            raise KeyError(f"capability not found: {capability_id}")
        approval = require_human_approval(
            site_id=site_id,
            capability_id=capability_id,
            capability=capability,
            params=params,
            confirmed=confirmed,
            human_approval=human_approval,
        )

        adapter = self._load_adapter(site_id)
        context = {
            "site_id": site_id,
            "root": str(self.root),
            "site_dir": str(self.sites_dir / site_id),
            "human_approval": approval.model_dump() if approval else None,
        }
        return adapter.run(capability_id, params, context)

    def _load_adapter(self, site_id: str) -> ModuleType:
        adapter_path = self.sites_dir / site_id / "adapter.py"
        if not adapter_path.exists():
            raise FileNotFoundError(f"adapter not found: {adapter_path}")
        module_name = f"api_anything_adapter_{site_id.replace('-', '_')}"
        spec = importlib.util.spec_from_file_location(module_name, adapter_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load adapter: {adapter_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module, "run"):
            raise AttributeError(f"adapter missing run(): {adapter_path}")
        return module
