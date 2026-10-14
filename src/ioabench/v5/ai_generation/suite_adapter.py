from __future__ import annotations

from typing import Any, Mapping, Protocol

from ioabench.v5.core.case import Case


class GeneratedSuiteAdapter(Protocol):
    """P3 selective integration: the suite-compiler interface a dynamic blueprint adapter must
    expose (ported verbatim from the Codex snapshot; the legacy T321Adapter is the reference
    implementation, NOT the dynamic-world capability ceiling)."""
    suite_id: str
    adapter_version: str

    def generator_constraints(self, *, subtype: str, difficulty: str) -> Mapping[str, Any]: ...
    def validate_blueprint(self, blueprint: Mapping[str, Any]) -> list[dict[str, str]]: ...
    def fidelity_report(self, blueprint: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def compile_pair(self, blueprint: Mapping[str, Any], *, seed: int) -> tuple[Case, Case]: ...
    def verify_arm_delta(self, control: Case, risk: Case) -> list[dict[str, str]]: ...
    def structural_signature(self, case: Case) -> Mapping[str, Any]: ...
