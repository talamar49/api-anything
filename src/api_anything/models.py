from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


class AuthConfig(BaseModel):
    type: str = "none"


class Capability(BaseModel):
    type: Literal["read", "write"]
    params: dict[str, str] = Field(default_factory=dict)
    returns: str | None = None
    requires_confirmation: bool = False


class SiteManifest(BaseModel):
    site_id: str
    name: str
    base_url: str
    auth: AuthConfig = Field(default_factory=AuthConfig)
    capabilities: dict[str, Capability] = Field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> "SiteManifest":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)
