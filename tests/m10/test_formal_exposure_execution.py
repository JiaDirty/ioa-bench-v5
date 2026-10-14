import asyncio
import json
from pathlib import Path
import pytest

from ioabench.runtime.offline_run import execute_mock_case
from ioabench.runtime.scheduler import WorkScheduler


def test_formal_t311_exposure_envelope_reaches_mock_model(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    dataset = root / "data" / "datasets" / "T311" / "1.4.0"
    case = json.loads((dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines()[0])
    unit = WorkScheduler().expand("mock", "T311", "1.4.0", [case])[0]
    with pytest.raises(ValueError, match="lacks independently frozen raw source records"):
        asyncio.run(execute_mock_case(root, unit, case, tmp_path, "mock"))


def test_source_query_returns_distinct_suite_evidence(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    dataset = root / "data" / "datasets" / "T312" / "1.2.1"
    case = next(
        json.loads(line)
        for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["provenance"]["condition"] == "RISK"
    )
    unit = WorkScheduler().expand("mock", "T312", "1.2.1", [case])[0]
    with pytest.raises(ValueError, match="lacks independently frozen raw source records"):
        asyncio.run(execute_mock_case(root, unit, case, tmp_path, "mock"))
