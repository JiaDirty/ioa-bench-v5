import asyncio
from dataclasses import asdict
from pathlib import Path

from ioabench.models import ModelProfile
from ioabench.runtime.deliberation_norm import (DeliberationBaseline, build_deliberation_case_from_skeleton,
                                                 execute_deliberation, run_deliberation_baseline)
from ioabench.runtime.disclosure_inference import (DisclosureBaseline, build_disclosure_case_from_skeleton,
                                                   execute_disclosure, run_disclosure_baseline)
from ioabench.runtime.human_agency_simulation import (AgencyBaseline, build_agency_case_from_skeleton,
                                                      execute_agency, run_agency_baseline)
from ioabench.runtime.incentive_reputation import (IncentiveReputationBaseline, build_incentive_case_from_skeleton,
                                                   execute_incentive_reputation, run_incentive_baseline)
from ioabench.runtime.network_propagation import (PropagationBaseline, build_propagation_case_from_skeleton,
                                                  execute_propagation, run_propagation_baseline)
from ioabench.suites.t331.generation import T331Generator
from ioabench.suites.t332.generation import T332Generator
from ioabench.suites.t333.generation import T333Generator
from ioabench.suites.t341.generation import T341Generator
from ioabench.suites.t342.generation import T342Generator
from ioabench.suites.t343.generation import T343Generator
from ioabench.suites.t351.generation import T351Generator
from ioabench.suites.t352.generation import T352Generator
from ioabench.suites.t361.generation import T361Generator
from ioabench.suites.t362.generation import T362Generator
from ioabench.suites.t363.generation import T363Generator

ROOT = Path(__file__).parents[2]


def generated(generator):
    return asdict(generator.generate(seed=3, mechanism_index=0, condition="RISK"))


def test_generated_world_adapters_preserve_suite_and_raw_payload():
    cases = {
        "T331": build_propagation_case_from_skeleton(generated(T331Generator())),
        "T342": build_propagation_case_from_skeleton(generated(T342Generator())),
        "T332": build_disclosure_case_from_skeleton(generated(T332Generator())),
        "T333": build_disclosure_case_from_skeleton(generated(T333Generator())),
        "T341": build_deliberation_case_from_skeleton(generated(T341Generator())),
        "T343": build_deliberation_case_from_skeleton(generated(T343Generator())),
        "T351": build_incentive_case_from_skeleton(generated(T351Generator())),
        "T352": build_incentive_case_from_skeleton(generated(T352Generator())),
        "T361": build_agency_case_from_skeleton(generated(T361Generator())),
        "T362": build_agency_case_from_skeleton(generated(T362Generator())),
        "T363": build_agency_case_from_skeleton(generated(T363Generator())),
    }
    assert set(cases) == {"T331", "T332", "T333", "T341", "T342", "T343", "T351", "T352", "T361", "T362", "T363"}
    for suite, case in cases.items():
        assert case["case_id"].startswith(suite)
        assert case["sut_payload"]
        assert case["oracle_payload"]["exposure_reachable"] is True


def test_generated_world_adapters_execute_through_specialized_runtimes():
    runners = {
        "T331": run_propagation_baseline,
        "T342": run_propagation_baseline,
        "T332": run_disclosure_baseline,
        "T333": run_disclosure_baseline,
        "T341": run_deliberation_baseline,
        "T343": run_deliberation_baseline,
        "T351": run_incentive_baseline,
        "T352": run_incentive_baseline,
        "T361": run_agency_baseline,
        "T362": run_agency_baseline,
        "T363": run_agency_baseline,
    }
    for suite, runner in runners.items():
        result = runner(ROOT, suite, "safe")
        replay = result["replay"]
        assert replay["scenario"]["test_id"] == suite
        assert replay["scenario"]["source_records"]
        assert replay["model_records"]
        assert replay["world_snapshot"]


def test_generated_cases_are_consumed_by_specialized_executors():
    cases = {
        "T331": (build_propagation_case_from_skeleton(generated(T331Generator())), execute_propagation, PropagationBaseline),
        "T342": (build_propagation_case_from_skeleton(generated(T342Generator())), execute_propagation, PropagationBaseline),
        "T332": (build_disclosure_case_from_skeleton(generated(T332Generator())), execute_disclosure, DisclosureBaseline),
        "T333": (build_disclosure_case_from_skeleton(generated(T333Generator())), execute_disclosure, DisclosureBaseline),
        "T341": (build_deliberation_case_from_skeleton(generated(T341Generator())), execute_deliberation, DeliberationBaseline),
        "T343": (build_deliberation_case_from_skeleton(generated(T343Generator())), execute_deliberation, DeliberationBaseline),
        "T351": (build_incentive_case_from_skeleton(generated(T351Generator())), execute_incentive_reputation, IncentiveReputationBaseline),
        "T352": (build_incentive_case_from_skeleton(generated(T352Generator())), execute_incentive_reputation, IncentiveReputationBaseline),
        "T361": (build_agency_case_from_skeleton(generated(T361Generator())), execute_agency, AgencyBaseline),
        "T362": (build_agency_case_from_skeleton(generated(T362Generator())), execute_agency, AgencyBaseline),
        "T363": (build_agency_case_from_skeleton(generated(T363Generator())), execute_agency, AgencyBaseline),
    }
    for suite, (case, executor, baseline_type) in cases.items():
        result = asyncio.run(executor(ROOT, case, baseline_type("safe"), ModelProfile("mock", "generated-world", {}, {}), run_id=f"{suite}-generated-safe"))
        assert result["replay"]["scenario"]["manifest"]["dataset_sha256"] == __import__("ioabench.hashing", fromlist=["canonical_sha256"]).canonical_sha256(case)
        assert result["score"]["task_utility"] is True, (suite, result["score"])
