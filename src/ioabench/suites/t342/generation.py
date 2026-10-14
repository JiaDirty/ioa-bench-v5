from ioabench.suites._vertical import SuiteDefinition, VerticalGenerator
from .spec import T342_MECHANISMS
from ioabench.suites._propagation_world import propagation_world, propagation_difficulty

T342_WORLDS = ("W01_ENTERPRISE_OPS", "W02_FINANCIAL_SERVICES", "W05_CLOUD_SOFTWARE")
DEFINITION = SuiteDefinition("T342", "Rumor Propagation", T342_MECHANISMS, T342_WORLDS, ("acceptance_rate", "forward_rate", "endorsement_rate", "rumor_reach", "source_retention", "verification_rate"), lambda risk, seed: {"proposition_truth": False, "rumor_present": risk, "source_chain_required": True, "rumor_seed": seed})

class T342Generator(VerticalGenerator):
    version = "t342-causal-v2"
    def __init__(self) -> None:
        super().__init__(DEFINITION)

    def generate(self, **kwargs):
        return propagation_world(super().generate(**kwargs), kwargs.get("mechanism_index", 0))

    difficulty_features = staticmethod(propagation_difficulty)
