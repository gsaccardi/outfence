"""Test the installed package from a fresh directory, with no source-tree imports."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

executable = shutil.which("outfence")
if executable is None:
    executable = str(Path(sys.executable).parent / "outfence")
env = dict(os.environ)
env.pop("PYTHONPATH", None)
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    commands = [
        ([executable, "--version"], 0),
        ([executable, "init", "policy.json", "--demo"], 0),
        ([executable, "check", "policy.json"], 0),
        ([executable, "demo", "--output", "enforce"], 2),
        ([sys.executable, "-m", "outfence", "demo", "--mode", "observe", "--output", "observe"], 2),
    ]
    for command, expected in commands:
        print(f"Smoke: {command}", flush=True)
        try:
            result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=20)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(f"Timed out: {command}\nstdout={exc.stdout!r}\nstderr={exc.stderr!r}") from exc
        if result.returncode != expected:
            raise AssertionError(f"{command}: {result.returncode}\n{result.stdout}\n{result.stderr}")
    policy = json.loads((root / "policy.json").read_text())
    policy["allow"].append({"host": "telemetry.example", "port": 80})
    (root / "policy.json").write_text(json.dumps(policy))
    result = subprocess.run([executable, "demo", "--policy", "policy.json", "--output", "allow-all"],
                            cwd=root, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Outfence report" in result.stdout
    assert "Allowed: 3 | Blocked: 0" in result.stdout
    for mode, expected in [("enforce", ["allowed", "allowed", "blocked"]),
                           ("observe", ["allowed", "allowed", "would_block"]),
                           ("allow-all", ["allowed"] * 3)]:
        report = json.loads((root / mode / "report.json").read_text())
        assert [e["action"] for e in report["events"]] == expected
        assert report["coverage"]["status"] == "proxy_only"
        assert not (root / mode / "report.html").exists()
print("Installed wheel smoke test passed: init, check, enforce, observe, edited policy.")
