import json
import os
import subprocess
import sys
from pathlib import Path


def run_cli(args, cwd: Path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    return subprocess.run(
        [sys.executable, "-m", "api_anything.cli", "--root", str(cwd), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )


def make_site(tmp_path: Path):
    site_dir = tmp_path / "sites" / "demo"
    site_dir.mkdir(parents=True)
    (site_dir / "manifest.yaml").write_text(
        """
site_id: demo
name: Demo
base_url: https://example.com
auth:
  type: none
capabilities:
  read_page:
    type: read
    params: {}
    returns: object
  send_message:
    type: write
    params: {}
    returns: object
    requires_confirmation: true
""".strip(),
        encoding="utf-8",
    )
    (site_dir / "adapter.py").write_text(
        """
def run(capability_id, params, context):
    return {"capability_id": capability_id, "params": params, "site_id": context["site_id"]}
""".strip(),
        encoding="utf-8",
    )


def test_batch_runs_multiple_capabilities_in_one_process(tmp_path):
    make_site(tmp_path)
    ops = [
        {"site_id": "demo", "capability_id": "read_page", "params": {"path": "a"}},
        {"site_id": "demo", "capability_id": "read_page", "params": {"path": "b"}},
    ]

    result = run_cli(["batch", "--ops", json.dumps(ops)], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert len(payload["results"]) == 2
    assert payload["results"][0]["ok"] is True
    assert payload["results"][1]["result"]["params"] == {"path": "b"}


def test_batch_blocks_unconfirmed_write(tmp_path):
    make_site(tmp_path)
    ops = [{"site_id": "demo", "capability_id": "send_message", "params": {}}]

    result = run_cli(["batch", "--ops", json.dumps(ops)], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["results"][0]["ok"] is False
    assert "requires confirmation" in payload["results"][0]["error"]
