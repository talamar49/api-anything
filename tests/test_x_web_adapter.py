import importlib.util
from pathlib import Path

import pytest

from api_anything.registry import Registry


ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / "examples" / "sites" / "x-web"


def load_adapter():
    spec = importlib.util.spec_from_file_location("x_web_adapter", SITE_DIR / "adapter.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_x_web_manifest_is_valid_and_writes_require_confirmation(tmp_path):
    site_root = tmp_path / "sites" / "x-web"
    site_root.mkdir(parents=True)
    for name in ["manifest.yaml", "adapter.py"]:
        (site_root / name).write_text((SITE_DIR / name).read_text(), encoding="utf-8")

    registry = Registry(tmp_path)
    caps = registry.get_capabilities("x-web")

    assert caps["login_status"].type == "read"
    assert caps["post"].type == "write"
    assert caps["post"].requires_confirmation is True
    assert caps["post_thread"].type == "write"
    assert caps["post_thread"].requires_confirmation is True

    with pytest.raises(PermissionError):
        registry.run_capability("x-web", "post", {"text": "hello"})


def test_x_web_adapter_validates_thread_posts():
    adapter = load_adapter()

    with pytest.raises(ValueError, match="posts must be"):
        adapter.run("post_thread", {"posts": []}, {})

    with pytest.raises(ValueError, match="text is required"):
        adapter.run("post", {"text": ""}, {})


def test_x_web_required_helper():
    adapter = load_adapter()

    assert adapter.required({"text": " hi "}, "text") == "hi"
    with pytest.raises(ValueError):
        adapter.required({}, "text")
