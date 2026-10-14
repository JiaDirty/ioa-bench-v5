import json
from pathlib import Path
def test_t362_mini_dataset_is_simulation_only() -> None:
    root = Path(__file__).parents[2]; dataset = root / "data" / "datasets" / "T362" / "dev-mini"; manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8")); cases = [json.loads(x) for x in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if x]; assert manifest["generation"]["validity"] == "SIMULATION_ONLY"; assert all(c["sut_payload"]["validity"] == "SIMULATION_ONLY" for c in cases)
