from ioabench.suites._vertical import SuiteDefinition, VerticalGenerator
from .spec import T323_MECHANISMS
from ioabench.suites._delegation_world import delegation_world, delegation_difficulty

T323_WORLDS = ("W01_ENTERPRISE_OPS", "W02_FINANCIAL_SERVICES", "W05_CLOUD_SOFTWARE")
DEFINITION = SuiteDefinition("T323", "Accountability Chain Break", T323_MECHANISMS, T323_WORLDS, ("provenance_check_rate", "unsafe_action_with_incomplete_chain", "reconstruction_request_rate", "task_success"), lambda risk, seed: {"provenance_complete": not risk, "accountability_gap": risk, "reconstruction_available": True})

class T323Generator(VerticalGenerator):
    version = "t323-causal-v2"

    def __init__(self) -> None:
        super().__init__(DEFINITION)

    def generate(self, **kwargs):
        return delegation_world(super().generate(**kwargs), kwargs.get("mechanism_index", 0))

    difficulty_features = staticmethod(delegation_difficulty)
