from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .agent_native import generate_skill_markdown, humanize, registry_doctor, site_agent_card
from .discovery import discover_site
from .hitl import params_sha256
from .registry import Registry
from .server import DEFAULT_ROOT


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=None, sort_keys=True))


def print_output(value: Any, *, human: bool = False) -> None:
    if human:
        print(humanize(value))
    else:
        print_json(value)


def approval_from_args(args: argparse.Namespace, params: dict[str, Any]) -> dict[str, Any] | None:
    if not (args.approved_by or args.approval_summary or args.reviewed_params_sha256):
        return None
    return {
        "approved": True,
        "approved_by": args.approved_by or "human",
        "action_summary": args.approval_summary or "human reviewed and approved this write action",
        "reviewed_params_sha256": args.reviewed_params_sha256 or params_sha256(params),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api-anything")
    parser.add_argument("--root", default=str(DEFAULT_ROOT), help="Registry root directory")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output (default)")
    parser.add_argument("--human", action="store_true", help="Human-readable output")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered sites")

    caps = subparsers.add_parser("caps", help="List site capabilities")
    caps.add_argument("site_id")

    run = subparsers.add_parser("run", help="Run a capability")
    run.add_argument("site_id")
    run.add_argument("capability_id")
    run.add_argument("--params", default="{}", help="JSON object parameters")
    run.add_argument("--confirmed", action="store_true", help="Allow confirmed write action")
    run.add_argument("--approved-by", help="Human approver for write actions")
    run.add_argument("--approval-summary", help="What the human reviewed and approved")
    run.add_argument("--reviewed-params-sha256", help="Optional SHA-256 of final params reviewed by the human")

    batch = subparsers.add_parser("batch", help="Run multiple capabilities in one process")
    batch.add_argument("--ops", required=True, help="JSON array of operations")
    batch.add_argument("--confirmed", action="store_true", help="Default confirmation for all write operations")

    discover = subparsers.add_parser("discover", help="Create a site adapter skeleton")
    discover.add_argument("--site-id", required=True)
    discover.add_argument("--name", required=True)
    discover.add_argument("--base-url", required=True)
    discover.add_argument("--capability", action="append", dest="capabilities", default=[])

    subparsers.add_parser("doctor", help="Validate registry/manifests/adapters for agent use")

    inspect = subparsers.add_parser("inspect", help="Show an agent-native contract for a site")
    inspect.add_argument("site_id")

    skill = subparsers.add_parser("skill", help="Generate/read AI skill metadata for a site")
    skill_sub = skill.add_subparsers(dest="skill_command", required=True)
    skill_generate = skill_sub.add_parser("generate", help="Generate SKILL.md for a site")
    skill_generate.add_argument("site_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root)
    registry = Registry(root)

    try:
        human = bool(args.human)
        if args.command == "list":
            print_output([site.model_dump() for site in registry.list_sites()], human=human)
            return 0
        if args.command == "caps":
            print_output({key: cap.model_dump() for key, cap in registry.get_capabilities(args.site_id).items()}, human=human)
            return 0
        if args.command == "run":
            params = json.loads(args.params)
            if not isinstance(params, dict):
                raise ValueError("--params must be a JSON object")
            print_output(
                registry.run_capability(
                    args.site_id,
                    args.capability_id,
                    params,
                    confirmed=args.confirmed,
                    human_approval=approval_from_args(args, params),
                ),
                human=human,
            )
            return 0
        if args.command == "batch":
            ops = json.loads(args.ops)
            if not isinstance(ops, list):
                raise ValueError("--ops must be a JSON array")
            results = []
            all_ok = True
            for index, op in enumerate(ops):
                try:
                    if not isinstance(op, dict):
                        raise ValueError("operation must be an object")
                    result = registry.run_capability(
                        op["site_id"],
                        op["capability_id"],
                        op.get("params") or {},
                        confirmed=bool(op.get("confirmed", args.confirmed)),
                        human_approval=op.get("human_approval"),
                    )
                    results.append({"index": index, "ok": True, "result": result})
                except Exception as exc:
                    all_ok = False
                    results.append({"index": index, "ok": False, "error": str(exc), "type": type(exc).__name__})
            print_output({"ok": all_ok, "results": results}, human=human)
            return 0
        if args.command == "discover":
            site = discover_site(
                root,
                site_id=args.site_id,
                name=args.name,
                base_url=args.base_url,
                capabilities=args.capabilities or ["read_page"],
            )
            print_output(site.model_dump(), human=human)
            return 0
        if args.command == "doctor":
            print_output(registry_doctor(registry), human=human)
            return 0
        if args.command == "inspect":
            print_output(site_agent_card(registry, args.site_id), human=human)
            return 0
        if args.command == "skill" and args.skill_command == "generate":
            path, text = generate_skill_markdown(registry, args.site_id)
            print_output({"path": str(path), "bytes": len(text.encode("utf-8"))}, human=human)
            return 0
    except Exception as exc:
        if getattr(args, "human", False):
            parser.exit(1, f"error: {exc}\n")
        print_json({"ok": False, "error": str(exc), "type": type(exc).__name__})
        return 1

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
