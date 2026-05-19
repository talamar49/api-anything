from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api_anything.registry import Registry
from api_anything.server import create_app


def write_site(root: Path, site_id: str = "demo-site", write_requires_confirmation: bool = True) -> Path:
    site_dir = root / "sites" / site_id
    site_dir.mkdir(parents=True)
    (site_dir / "manifest.yaml").write_text(
        f"""
site_id: {site_id}
name: Demo Site
base_url: https://example.com
auth:
  type: none
capabilities:
  echo:
    type: read
    params:
      text: string
    returns: object
  send_message:
    type: write
    params:
      chat: string
      text: string
    requires_confirmation: {str(write_requires_confirmation).lower()}
""".strip(),
        encoding="utf-8",
    )
    (site_dir / "adapter.py").write_text(
        """
def run(capability_id, params, context):
    if capability_id == "echo":
        return {"echo": params["text"], "site": context["site_id"]}
    if capability_id == "send_message":
        return {"sent": True, "chat": params["chat"], "text": params["text"]}
    raise ValueError(f"unknown capability: {capability_id}")
""".strip(),
        encoding="utf-8",
    )
    return site_dir


def test_registry_lists_sites_from_manifest(tmp_path):
    write_site(tmp_path)
    registry = Registry(tmp_path)

    sites = registry.list_sites()

    assert [site.site_id for site in sites] == ["demo-site"]
    assert sites[0].name == "Demo Site"


def test_registry_returns_capabilities(tmp_path):
    write_site(tmp_path)
    registry = Registry(tmp_path)

    capabilities = registry.get_capabilities("demo-site")

    assert set(capabilities.keys()) == {"echo", "send_message"}
    assert capabilities["send_message"].type == "write"
    assert capabilities["send_message"].requires_confirmation is True


def test_run_read_capability_loads_adapter(tmp_path):
    write_site(tmp_path)
    registry = Registry(tmp_path)

    result = registry.run_capability("demo-site", "echo", {"text": "hello"})

    assert result == {"echo": "hello", "site": "demo-site"}


def test_write_capability_requires_explicit_confirmation(tmp_path):
    write_site(tmp_path)
    registry = Registry(tmp_path)
    params = {"chat": "Alice", "text": "hi"}

    with pytest.raises(PermissionError, match="requires confirmation"):
        registry.run_capability("demo-site", "send_message", params)

    with pytest.raises(PermissionError, match="human approval required"):
        registry.run_capability("demo-site", "send_message", params, confirmed=True)

    result = registry.run_capability(
        "demo-site",
        "send_message",
        params,
        confirmed=True,
        human_approval={
            "approved": True,
            "approved_by": "Alice",
            "action_summary": "Send test message to Alice",
        },
    )
    assert result["sent"] is True


def test_fastapi_endpoints_expose_registry(tmp_path):
    write_site(tmp_path)
    client = TestClient(create_app(tmp_path))

    assert client.get("/health").json() == {"ok": True}
    assert client.get("/sites").json()[0]["site_id"] == "demo-site"
    assert "echo" in client.get("/sites/demo-site/capabilities").json()

    response = client.post("/sites/demo-site/run/echo", json={"params": {"text": "api"}})
    assert response.status_code == 200
    assert response.json()["result"] == {"echo": "api", "site": "demo-site"}


def test_fastapi_rejects_unconfirmed_write(tmp_path):
    write_site(tmp_path)
    client = TestClient(create_app(tmp_path))
    params = {"chat": "Alice", "text": "hi"}

    response = client.post(
        "/sites/demo-site/run/send_message",
        json={"params": params},
    )

    assert response.status_code == 403
    assert "requires confirmation" in response.json()["detail"]

    response = client.post(
        "/sites/demo-site/run/send_message",
        json={"params": params, "confirmed": True},
    )

    assert response.status_code == 403
    assert "human approval required" in response.json()["detail"]


def test_fastapi_allows_write_with_human_approval(tmp_path):
    write_site(tmp_path)
    client = TestClient(create_app(tmp_path))
    params = {"chat": "Alice", "text": "hi"}

    response = client.post(
        "/sites/demo-site/run/send_message",
        json={
            "params": params,
            "confirmed": True,
            "human_approval": {
                "approved": True,
                "approved_by": "Alice",
                "action_summary": "Send approved test message",
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["result"]["sent"] is True

def test_fastapi_requires_api_token_when_configured(tmp_path, monkeypatch):
    write_site(tmp_path)
    monkeypatch.setenv("API_ANYTHING_TOKEN", "test-token")
    client = TestClient(create_app(tmp_path))

    assert client.get("/health").status_code == 200
    assert client.get("/sites").status_code == 401

    response = client.get("/sites", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json()[0]["site_id"] == "demo-site"
