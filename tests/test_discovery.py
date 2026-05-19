from pathlib import Path

from fastapi.testclient import TestClient

from api_anything.discovery import discover_site
from api_anything.registry import Registry
from api_anything.server import create_app


def test_discover_site_creates_manifest_and_adapter_stub(tmp_path):
    site = discover_site(
        tmp_path,
        site_id="example-com",
        name="Example",
        base_url="https://example.com",
        capabilities=["read_page", "submit_form"],
    )

    assert site.site_id == "example-com"
    assert (tmp_path / "sites" / "example-com" / "manifest.yaml").exists()
    assert (tmp_path / "sites" / "example-com" / "adapter.py").exists()

    registry = Registry(tmp_path)
    caps = registry.get_capabilities("example-com")
    assert set(caps) == {"read_page", "submit_form"}
    assert caps["read_page"].type == "read"
    assert caps["submit_form"].type == "write"
    assert caps["submit_form"].requires_confirmation is True


def test_discover_site_refuses_to_overwrite_existing_site(tmp_path):
    discover_site(tmp_path, site_id="example-com", name="Example", base_url="https://example.com")

    try:
        discover_site(tmp_path, site_id="example-com", name="Example 2", base_url="https://example.org")
    except FileExistsError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("expected FileExistsError")


def test_discover_endpoint_creates_site(tmp_path):
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/discover",
        json={
            "site_id": "example-com",
            "name": "Example",
            "base_url": "https://example.com",
            "capabilities": ["read_page"],
        },
    )

    assert response.status_code == 200
    assert response.json()["site_id"] == "example-com"
    assert client.get("/sites/example-com/capabilities").status_code == 200
