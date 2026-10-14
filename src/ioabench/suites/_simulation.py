from dataclasses import dataclass
from typing import Any, Callable, Mapping

from ._vertical import VerticalExposureController, VerticalGenerator, VerticalScenario

SIMULATION_ONLY = "SIMULATION_ONLY"


class SimulationGenerator(VerticalGenerator):
    # SIMULATION_ONLY is carried on case/scenario metadata (runtime adapters,
    # replay scenario, eligibility) - never inside the model-visible payload,
    # where a governance label would read as a benchmark leak.
    def generate(self, **kwargs: Any):
        return super().generate(**kwargs)


@dataclass
class SyntheticPersonaRuntime:
    persona_id: str
    seed: int
    phase: str = "baseline"
    state: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        self.state = {"persona_id": self.persona_id, "seed": self.seed, "phase": self.phase, "validity": SIMULATION_ONLY}

    def advance(self, phase: str) -> Mapping[str, Any]:
        self.phase = phase
        assert self.state is not None
        self.state["phase"] = phase
        return dict(self.state)

    def reset(self) -> Mapping[str, Any]:
        self.phase = "baseline"
        return self.advance("baseline")

    def output(self, value: Any) -> dict[str, Any]:
        return {"value": value, "persona_id": self.persona_id, "phase": self.phase, "validity": SIMULATION_ONLY}


@dataclass(frozen=True)
class SimulationScenario(VerticalScenario):
    simulation_only: bool = True

    def document(self) -> dict[str, Any]:
        value = super().document()
        value["simulation_only"] = self.simulation_only
        value["validity"] = SIMULATION_ONLY
        value["claim_boundary"] = "synthetic persona findings only; no real-human inference"
        return value


class SimulationExposureController(VerticalExposureController):
    def expose(self, scenario: SimulationScenario, receive_model_input: Callable[[Mapping[str, Any]], Any]) -> Any:
        result = super().expose(scenario, receive_model_input)
        self.proof_events.append({"event_type": "simulation.label", "validity": SIMULATION_ONLY})
        return result
