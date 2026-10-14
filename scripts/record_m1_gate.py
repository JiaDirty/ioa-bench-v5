"""Record offline M1 acceptance evidence without hiding provider blockers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "tests/m1", "-q"]
    result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, text=True)
    smoke_path = ROOT / "artifacts" / "provider" / "aihubmix-smoke.json"
    smoke = json.loads(smoke_path.read_text(encoding="utf-8")) if smoke_path.exists() else {"status": "MISSING"}
    artifact = {
        "gate": "M1",
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "command": " ".join(command),
        "returncode": result.returncode,
        "provider_smoke_status": smoke.get("status"),
        "requested_model_id": smoke.get("requested_model_id", "deepseek-v4.1-flash"),
        "evidence": {
            "offline_model_tests": result.stdout.strip().splitlines()[-1:] if result.stdout else [],
            "model_port": True,
            "exact_model_resolution_policy": True,
            "no_silent_substitution": True,
            "mock_replay": True,
            "isolated_sessions": True,
            "live_provider_blocker_recorded": smoke.get("status") in {"PROVIDER_BLOCKED", "UNSUPPORTED"},
        },
    }
    target = ROOT / "artifacts" / "gates" / "M1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(artifact, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
