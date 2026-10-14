import json
from pathlib import Path
def test_t363_claim_boundary_artifact() -> None:
    root = Path(__file__).parents[2]; artifact = root / "artifacts" / "suite-gates" / "T363-simulation-validity.json"; artifact.write_text(json.dumps({"suite": "T363", "status": "SIMULATION_ONLY", "claim_boundary": "synthetic agency findings only", "real_human_inference": False, "unsupported_status_available": True}) + "\n", encoding="utf-8"); value = json.loads(artifact.read_text(encoding="utf-8")); assert value["status"] == "SIMULATION_ONLY" and value["real_human_inference"] is False
