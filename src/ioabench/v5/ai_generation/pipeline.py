"""Shared candidate pipeline for typed dynamic-suite blueprint adapters.

The pipeline owns only the common checks. Suite adapters own construct-specific semantics,
Ground Truth and scoring. A blueprint is never accepted by this module unless the adapter
maps it to a CONTROL/RISK pair and the existing deterministic pair gate passes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ioabench.models import ModelProfile
from ioabench.v5.ai_generation.suite_adapter import GeneratedSuiteAdapter
from ioabench.v5.core.case import Case
from ioabench.v5.dynamic.gates import check_pair_dynamic
from ioabench.v5.dynamic.runner import run_dynamic_case, _resolve_scenario


class CandidateRejected(ValueError):
    """Deterministic candidate rejection with serializable findings."""

    def __init__(self, stage: str, findings: Sequence[Mapping[str, Any]]) -> None:
        self.stage = stage
        self.findings = [dict(item) if isinstance(item, Mapping) else {"reason": str(item)} for item in findings]
        super().__init__(f"{stage}: {self.findings}")


@dataclass(frozen=True)
class SuitePipelineSpec:
    suite_id: str
    adapter: GeneratedSuiteAdapter
    slice_module: Any
    scenario_factory: Callable[[], Any]
    scorer: Callable[..., Any]
    policies: Mapping[str, Any]
    expected: Mapping[str, Any]
    timing_rules: Sequence[Any]


def suite_spec(suite_id: str, *, typed: bool = False) -> SuitePipelineSpec:
    """Resolve a supported structure; typed mode exposes only implemented world knobs."""
    from ioabench.v5.dynamic.registry import get_adapter
    from ioabench.v5.ai_generation.runtime_adapter import RuntimeGenerationAdapter

    module = get_adapter(suite_id + "-DYNA" if "-" not in suite_id else suite_id)
    if typed:
        from ioabench.v5.ai_generation.bounded_compiler import BoundedWorldCompiler, FACTORS
        from ioabench.v5.ai_generation.t312_compiler import T312DynaCompiler
        from ioabench.v5.ai_generation.t321_dyna_compiler import T321DynaCompiler
        from ioabench.v5.ai_generation.t331_compiler import T331DynaCompiler
        from ioabench.v5.ai_generation.t352_compiler import T352DynaCompiler
        compilers = {"T312-DYNA": T312DynaCompiler, "T321-DYNA": T321DynaCompiler, "T331-DYNA": T331DynaCompiler,
                     "T352-DYNA": T352DynaCompiler}
        compilers.update({suite: lambda suite=suite: BoundedWorldCompiler(suite) for suite in FACTORS})
        from ioabench.v5.ai_generation.t311_compiler import T311DynaCompiler
        from ioabench.v5.ai_generation.t351_compiler import T351DynaCompiler
        compilers["T311-DYNA"] = T311DynaCompiler
        compilers["T351-DYNA"] = T351DynaCompiler
        from ioabench.v5.ai_generation.t353_compiler import T353DynaCompiler
        compilers["T353-DYNA"] = T353DynaCompiler
        from ioabench.v5.ai_generation.t362_compiler import T362DynaCompiler
        compilers["T362-DYNA"] = T362DynaCompiler
        from ioabench.v5.ai_generation.t323_compiler import T323DynaCompiler
        compilers["T323-DYNA"] = T323DynaCompiler
        from ioabench.v5.ai_generation.t322_compiler import T322DynaCompiler
        from ioabench.v5.ai_generation.t343_compiler import T343DynaCompiler
        compilers["T322-DYNA"] = T322DynaCompiler
        compilers["T343-DYNA"] = T343DynaCompiler
        from ioabench.v5.ai_generation.t313_compiler import T313DynaCompiler
        compilers["T313-DYNA"] = T313DynaCompiler
        if module.SLICE_ID not in compilers:
            raise ValueError(f"typed world compiler unavailable for {module.SLICE_ID}; use declared enrichment")
        adapter = compilers[module.SLICE_ID]()
    else:
        adapter = RuntimeGenerationAdapter(module.SLICE_ID)
    return SuitePipelineSpec(module.SLICE_ID, adapter, module, lambda: _resolve_scenario(module),
                             module.score, module.policies(), module.EXPECTED_REFERENCE,
                             getattr(module, "TIMING_RULES", ()))


def compile_and_gate(spec: SuitePipelineSpec, blueprint: Mapping[str, Any], *, seed: int) -> dict[str, Any]:
    """Validate, compile and run the deterministic pair gate for one candidate."""
    findings = list(spec.adapter.validate_blueprint(blueprint))
    fidelity = dict(spec.adapter.fidelity_report(blueprint))
    if findings or fidelity.get("gaps"):
        raise CandidateRejected("BLUEPRINT_OR_FIDELITY", [*findings, *fidelity.get("gaps", [])])
    try:
        control, risk = spec.adapter.compile_pair(blueprint, seed=seed)
    except ValueError as exc:
        raise CandidateRejected("COMPILE_FIDELITY", [{"code": "INVALID_PROPOSAL", "reason": str(exc)}]) from exc
    arm_findings = list(spec.adapter.verify_arm_delta(control, risk))
    if arm_findings:
        raise CandidateRejected("ARM_DELTA", arm_findings)
    if getattr(spec.adapter, "requires_execution_fidelity", False) and not callable(
            getattr(spec.scenario_factory(), "execution_fidelity", None)):
        raise CandidateRejected("CAPABILITY_GAP", [{"reason": "primitive has no executable consumer proof"}])
    gate = check_pair_dynamic(control, risk, scenario=spec.scenario_factory(), scorer=spec.scorer,
                             policies=spec.policies, expected=spec.expected,
                             fine_arm_delta=spec.adapter.verify_arm_delta)
    if not gate.get("passed"):
        raise CandidateRejected("PAIR_GATE", gate.get("failures", []))
    return {"suite_id": spec.suite_id, "seed": seed, "blueprint": dict(blueprint),
            "control": control, "risk": risk, "fidelity": fidelity, "gate": gate,
            "structural_signature": spec.adapter.structural_signature(control)}


def run_reference_policies(spec: SuitePipelineSpec, run_root: Path, pair: Mapping[str, Case], *,
                           run_id: str, profile: ModelProfile, parameters: Mapping[str, Any] | None = None
                           ) -> list[dict[str, Any]]:
    """Execute the configured reference policies through the normal dynamic runner."""
    parameters = dict(parameters or {"temperature": 0.0})
    results: list[dict[str, Any]] = []
    for policy_name, policy in spec.policies.items():
        for arm, case in pair.items():
            results.append(run_dynamic_case(
                run_root, case, spec.slice_module, policy, profile,
                run_id=f"{run_id}-{policy_name}-{arm.lower()}",
                parameters=parameters, timing_rules=spec.timing_rules))
    return results
