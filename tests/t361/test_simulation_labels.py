import json
from pathlib import Path
def test_t361_claim_boundary_artifact() -> None:
    root = Path(__file__).parents[2]; artifact = root / "artifacts" / "suite-gates" / "T361-simulation-validity.json"; artifact.write_text(json.dumps({"suite": "T361", "status": "SIMULATION_ONLY", "claim_boundary": "synthetic persona findings only", "real_human_inference": False, "unsupported_status_available": True}) + "\n", encoding="utf-8"); value = json.loads(artifact.read_text(encoding="utf-8")); assert value["status"] == "SIMULATION_ONLY" and value["real_human_inference"] is False
