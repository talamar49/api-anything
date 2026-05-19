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


def test_cli_discover_and_list(tmp_path):
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
        ],
        tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["site_id"] == "example-com"

    result = run_cli(["list"], tmp_path)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)[0]["site_id"] == "example-com"


def test_cli_run_capability(tmp_path):
    run_cli([
        "discover",
        "--site-id",
        "example-com",
        "--name",
        "Example",
        "--base-url",
        "https://example.com",
    ], tmp_path)

    result = run_cli(["run", "example-com", "read_page", "--params", '{"x": 1}'], tmp_path)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "stub"
    assert payload["params"] == {"x": 1}
