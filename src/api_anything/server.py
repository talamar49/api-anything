from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .discovery import discover_site
from .hitl import HumanApproval
from .registry import Registry


DEFAULT_ROOT = Path.home() / ".api-anything"


def require_api_token(authorization: str | None = Header(default=None)) -> None:
    """Require Bearer auth only when API_ANYTHING_TOKEN is configured.

    API Anything is local-first, so development/test runs stay zero-config.
    Any network-exposed deployment should set API_ANYTHING_TOKEN and serve only
    behind TLS/reverse proxy.
    """
    expected = os.getenv("API_ANYTHING_TOKEN")
    if not expected:
        return
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="missing or invalid API token")


class RunRequest(BaseModel):
    params: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    human_approval: HumanApproval | None = None


class DiscoverRequest(BaseModel):
    site_id: str
    name: str
    base_url: str
    capabilities: list[str] = Field(default_factory=lambda: ["read_page"])


def create_app(root: str | Path = DEFAULT_ROOT) -> FastAPI:
    registry = Registry(root)
    app = FastAPI(title="API Anything", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/sites", dependencies=[Depends(require_api_token)])
    def sites() -> list[dict[str, Any]]:
        return [site.model_dump() for site in registry.list_sites()]

    @app.post("/discover", dependencies=[Depends(require_api_token)])
    def discover(request: DiscoverRequest) -> dict[str, Any]:
        try:
            site = discover_site(
                root,
                site_id=request.site_id,
                name=request.name,
                base_url=request.base_url,
                capabilities=request.capabilities,
            )
            return site.model_dump()
        except FileExistsError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/sites/{site_id}/capabilities", dependencies=[Depends(require_api_token)])
    def capabilities(site_id: str) -> dict[str, Any]:
        try:
            return {key: cap.model_dump() for key, cap in registry.get_capabilities(site_id).items()}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/sites/{site_id}/run/{capability_id}", dependencies=[Depends(require_api_token)])
    def run(site_id: str, capability_id: str, request: RunRequest) -> dict[str, Any]:
        try:
            result = registry.run_capability(
                site_id,
                capability_id,
                request.params,
                confirmed=request.confirmed,
                human_approval=request.human_approval.model_dump() if request.human_approval else None,
            )
            return {"result": result}
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()
