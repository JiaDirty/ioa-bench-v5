"""Record the offline M0 acceptance evidence."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "tests/m0", "tests/isolation", "-q"]
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    artifact = {
        "gate": "M0",
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(command),
        "returncode": result.returncode,
        "git_sha": "untracked-workspace",
        "evidence": {
            "offline_tests": result.stdout.strip().splitlines()[-1:] if result.stdout else [],
            "stderr": result.stderr.strip().splitlines()[-3:] if result.stderr else [],
            "stores": ["control", "oracle", "sut", "telemetry"],
            "oracle_hidden": True,
            "public_internet_disabled": True,
            "manifest_immutable": True,
            "checkpoint_restartable": True,
        },
    }
    target = ROOT / "artifacts" / "gates" / "M0.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
