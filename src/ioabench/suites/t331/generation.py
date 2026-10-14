from ioabench.suites._vertical import SuiteDefinition, VerticalGenerator
from .spec import T331_MECHANISMS
from ioabench.suites._propagation_world import propagation_world, propagation_difficulty

T331_WORLDS = ("W01_ENTERPRISE_OPS", "W02_FINANCIAL_SERVICES", "W05_CLOUD_SOFTWARE")
DEFINITION = SuiteDefinition(
    "T331", "Cross-System Cascade", T331_MECHANISMS, T331_WORLDS,
    ("cascade_size", "propagation_depth", "R_agent", "verification_before_forward", "containment_rate", "task_success"),
    lambda risk, seed: {"local_error": risk, "cascade_truth": not risk, "topology_seed": seed},
)


class T331Generator(VerticalGenerator):
    version = "t331-causal-v2"
    def __init__(self) -> None:
        super().__init__(DEFINITION)

    def generate(self, **kwargs):
        return propagation_world(super().generate(**kwargs), kwargs.get("mechanism_index", 0))

    difficulty_features = staticmethod(propagation_difficulty)
