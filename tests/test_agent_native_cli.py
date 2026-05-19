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


def discover_example(root: Path):
    result = run_cli(
        [
            "discover",
            "--site-id",
            "example-com",
            "--name",
            "Example",
            "--base-url",
            "https://example.com",
            "--capability",
            "read_page",
            "--capability",
            "send_message",
        ],
        root,
    )
    assert result.returncode == 0, result.stderr


def test_doctor_reports_registry_and_site_health(tmp_path):
    discover_example(tmp_path)

    result = run_cli(["doctor"], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["summary"]["sites"] == 1
    assert payload["sites"][0]["site_id"] == "example-com"
    assert payload["sites"][0]["adapter_exists"] is True
    assert payload["sites"][0]["manifest_valid"] is True


def test_inspect_outputs_agent_native_contract(tmp_path):
    discover_example(tmp_path)

    result = run_cli(["inspect", "example-com"], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["site_id"] == "example-com"
    assert payload["agent_native"] is True
    assert payload["entry_point"] == "api-anything run example-com <capability_id>"
    assert payload["interfaces"]["cli"] is True
    assert payload["interfaces"]["json"] is True
    assert "read_page" in payload["capabilities"]
    assert payload["capabilities"]["send_message"]["requires_confirmation"] is True


def test_skill_generate_writes_agent_skill(tmp_path):
    discover_example(tmp_path)

    result = run_cli(["skill", "generate", "example-com"], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    skill_path = Path(payload["path"])
    assert skill_path.exists()
    text = skill_path.read_text(encoding="utf-8")
    assert "api-anything-example-com" in text
    assert "api-anything run example-com read_page" in text
    assert "requires confirmation" in text


def test_human_output_is_available_but_json_remains_default(tmp_path):
    discover_example(tmp_path)

    json_result = run_cli(["inspect", "example-com"], tmp_path)
    assert json.loads(json_result.stdout)["site_id"] == "example-com"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    human_result = subprocess.run(
        [sys.executable, "-m", "api_anything.cli", "--root", str(tmp_path), "--human", "inspect", "example-com"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    assert human_result.returncode == 0, human_result.stderr
    assert "Example" in human_result.stdout
    assert "Capabilities" in human_result.stdout
