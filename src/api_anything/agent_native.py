from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import Capability, SiteManifest
from .registry import Registry


def registry_doctor(registry: Registry) -> dict[str, Any]:
    """Return machine-readable health for the local API Anything registry."""
    root = registry.root
    sites_dir = registry.sites_dir
    site_reports: list[dict[str, Any]] = []
    ok = True

    for site_dir in sorted(sites_dir.glob("*")) if sites_dir.exists() else []:
        if not site_dir.is_dir():
            continue
        manifest_path = site_dir / "manifest.yaml"
        adapter_path = site_dir / "adapter.py"
        report: dict[str, Any] = {
            "site_id": site_dir.name,
            "manifest_exists": manifest_path.exists(),
            "adapter_exists": adapter_path.exists(),
            "manifest_valid": False,
            "capabilities": 0,
            "writes_require_confirmation": True,
            "errors": [],
        }
        try:
            manifest = SiteManifest.from_file(manifest_path)
            report["manifest_valid"] = True
            report["site_id"] = manifest.site_id
            report["capabilities"] = len(manifest.capabilities)
            unsafe_writes = [
                cid
                for cid, cap in manifest.capabilities.items()
                if cap.type == "write" and not cap.requires_confirmation
            ]
            report["writes_require_confirmation"] = not unsafe_writes
            if unsafe_writes:
                report["errors"].append(
                    f"write capabilities without confirmation: {', '.join(unsafe_writes)}"
                )
        except Exception as exc:  # pragma: no cover - exact parser messages are dependency-specific
            report["errors"].append(str(exc))
        if not report["manifest_exists"] or not report["adapter_exists"] or report["errors"]:
            ok = False
        site_reports.append(report)

    return {
        "ok": ok,
        "root": str(root),
        "sites_dir": str(sites_dir),
        "summary": {
            "sites": len(site_reports),
            "valid_sites": sum(1 for site in site_reports if site["manifest_valid"] and site["adapter_exists"]),
        },
        "sites": site_reports,
    }


def capability_contract(capability: Capability) -> dict[str, Any]:
    risk = "write" if capability.type == "write" else "read"
    return {
        "type": capability.type,
        "risk": risk,
        "params": capability.params,
        "returns": capability.returns,
        "requires_confirmation": capability.requires_confirmation,
        "agent_rules": [
            "may run automatically" if capability.type == "read" else "must require explicit user confirmation",
            "return structured JSON",
            "include evidence/receipt when adapter supports it",
        ],
    }


def site_agent_card(registry: Registry, site_id: str) -> dict[str, Any]:
    manifest = registry.get_site(site_id)
    return {
        "site_id": manifest.site_id,
        "name": manifest.name,
        "base_url": manifest.base_url,
        "agent_native": True,
        "standard": "api-anything-agent-harness-v0",
        "entry_point": f"api-anything run {manifest.site_id} <capability_id>",
        "interfaces": {
            "cli": True,
            "json": True,
            "http": True,
            "human": True,
        },
        "auth": manifest.auth.model_dump(),
        "capabilities": {
            capability_id: capability_contract(capability)
            for capability_id, capability in manifest.capabilities.items()
        },
        "safety": {
            "read_write_separated": True,
            "writes_need_confirmation": all(
                cap.type != "write" or cap.requires_confirmation
                for cap in manifest.capabilities.values()
            ),
            "secrets_policy": "adapters must not persist or echo credentials",
        },
    }


def generate_skill_markdown(registry: Registry, site_id: str) -> tuple[Path, str]:
    card = site_agent_card(registry, site_id)
    site_dir = registry.sites_dir / site_id
    skill_dir = site_dir / "skills"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skill_dir / "SKILL.md"

    cap_lines = []
    examples = []
    for capability_id, cap in card["capabilities"].items():
        suffix = " — requires confirmation" if cap["requires_confirmation"] else ""
        cap_lines.append(f"- `{capability_id}` ({cap['type']}){suffix}")
        confirm = " --confirmed" if cap["requires_confirmation"] else ""
        examples.append(
            f"api-anything run {site_id} {capability_id} --params '{{}}'{confirm}"
        )

    text = f"""---
name: api-anything-{site_id}
description: Agent-native API Anything harness for {card['name']}.
---

# api-anything-{site_id}

Agent-native harness for **{card['name']}**.

Base URL: {card['base_url']}
Standard: `{card['standard']}`

## Capabilities

{chr(10).join(cap_lines)}

## Usage

JSON is the default output for agents.

```bash
api-anything inspect {site_id}
```

```bash
{chr(10).join(examples)}
```

## Agent Rules

- Inspect before run: `api-anything inspect {site_id}`.
- Run reads freely.
- Writes/sends/deletes/payments require confirmation.
- Treat output as structured JSON.
- Do not store or echo credentials.
"""
    skill_path.write_text(text, encoding="utf-8")
    return skill_path, text


def humanize(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(_humanize_site(item) if isinstance(item, dict) else str(item) for item in value)
    if isinstance(value, dict):
        if "site_id" in value and "capabilities" in value:
            return _humanize_site(value)
        if "ok" in value and "sites" in value:
            lines = [f"Registry: {'OK' if value['ok'] else 'BROKEN'}", f"Sites: {value['summary']['sites']}"]
            for site in value["sites"]:
                status = "OK" if site["manifest_valid"] and site["adapter_exists"] and not site["errors"] else "BROKEN"
                lines.append(f"- {site['site_id']}: {status} ({site['capabilities']} capabilities)")
            return "\n".join(lines)
    return str(value)


def _humanize_site(site: dict[str, Any]) -> str:
    lines = [f"{site.get('name', site.get('site_id'))} ({site.get('site_id')})"]
    if site.get("base_url"):
        lines.append(f"URL: {site['base_url']}")
    if site.get("capabilities"):
        lines.append("Capabilities:")
        caps = site["capabilities"]
        if isinstance(caps, dict):
            for cap_id, cap in caps.items():
                confirm = " confirmation" if cap.get("requires_confirmation") else ""
                lines.append(f"- {cap_id}: {cap.get('type')}{confirm}")
    return "\n".join(lines)
