"""Small deterministic service catalog for synthetic worlds."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ServiceSpec:
    service_id: str
    domain: str
    operations: tuple[str, ...]


class SyntheticService:
    def __init__(self, spec: ServiceSpec, seed: int) -> None:
        self.spec = spec
        self.seed = seed
        self._state: dict[str, Any] = {"seed": seed, "revision": 0, "records": {}}

    def execute(self, operation: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if operation not in self.spec.operations:
            raise ValueError(f"operation unavailable on {self.spec.service_id}: {operation}")
        if operation in {"read", "query", "lookup"}:
            key = str(arguments.get("key", "default"))
            return {"service_id": self.spec.service_id, "key": key, "value": deepcopy(self._state["records"].get(key))}
        key = str(arguments.get("key", "default"))
        self._state["records"][key] = deepcopy(arguments.get("value", {"operation": operation}))
        self._state["revision"] += 1
        return {"service_id": self.spec.service_id, "key": key, "revision": self._state["revision"], "status": "OK"}

    def snapshot(self) -> Mapping[str, Any]:
        return {"spec": self.spec.service_id, "domain": self.spec.domain, "state": deepcopy(self._state)}


def build_default_services(seed: int = 1) -> dict[str, SyntheticService]:
    specs = (
        ServiceSpec("enterprise.records", "enterprise", ("read", "update", "approve")),
        ServiceSpec("finance.review", "finance", ("read", "query", "approve", "reject")),
        ServiceSpec("research.evidence", "research", ("read", "query", "annotate")),
        ServiceSpec("logistics.shipments", "logistics", ("read", "update", "assign")),
        ServiceSpec("software.incidents", "software-cloud", ("read", "create", "close", "deploy")),
        ServiceSpec("knowledge.email", "knowledge-email", ("read", "query", "send", "forward")),
    )
    return {spec.service_id: SyntheticService(spec, seed + index) for index, spec in enumerate(specs)}
