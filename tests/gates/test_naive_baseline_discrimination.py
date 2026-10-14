import asyncio
import json
from pathlib import Path

import yaml
import pytest

from ioabench.runtime.offline_run import SUITES, execute_mock_case
from ioabench.runtime.scheduler import WorkScheduler


def test_naive_baseline_triggers_each_suite_scorer(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    pack = yaml.safe_load((root / "data" / "datasets" / "DATASET_PACK_v2.yaml").read_text(encoding="utf-8"))
    outcomes: dict[str, str] = {}
    for suite in SUITES:
        version = str(pack["suites"][suite]["version"])
        dataset = root / "data" / "datasets" / suite / version
        cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
        case = next(item for item in cases if item["provenance"]["condition"] == "RISK")
        unit = WorkScheduler().expand("naive", suite, version, [case])[0]
        with pytest.raises(ValueError, match="lacks independently frozen raw source records"):
            asyncio.run(execute_mock_case(root, unit, case, tmp_path / suite, "naive"))
        outcomes[suite] = "LEGACY_CONSTRUCT_INVALID"
    assert set(outcomes) == set(SUITES)
    assert all(outcome == "LEGACY_CONSTRUCT_INVALID" for outcome in outcomes.values())


def test_safe_mock_baseline_is_not_scored_as_unsafe(tmp_path: Path) -> None:
    root = Path(__file__).parents[2]
    pack = yaml.safe_load((root / "data" / "datasets" / "DATASET_PACK_v2.yaml").read_text(encoding="utf-8"))
    for suite in SUITES:
        version = str(pack["suites"][suite]["version"])
        dataset = root / "data" / "datasets" / suite / version
        cases = [json.loads(line) for line in (dataset / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]
        case = next(item for item in cases if item["provenance"]["condition"] == "RISK")
        unit = WorkScheduler().expand("mock", suite, version, [case])[0]
        with pytest.raises(ValueError, match="lacks independently frozen raw source records"):
            asyncio.run(execute_mock_case(root, unit, case, tmp_path / suite, "mock"))
