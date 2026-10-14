"""v5 case schema: a visible world, a hidden oracle and declared mechanism slots.

A v5 case is the unit of measurement. The fields the runtime may render to a tested agent live
under ``world``; evaluator-only facts live under ``oracle`` and are never handed to tool handlers,
policies or prompts. ``mechanism_slots`` are JSON pointers into ``world`` naming the only paths a
CONTROL/RISK pair is allowed to differ in (ADR-V5-000 P5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ioabench.hashing import canonical_sha256

CASE_SCHEMA_VERSION = "ioabench.v5.case/1"
SUITES = ("T311", "T312", "T313", "T321", "T322", "T323", "T331", "T332", "T333",
          "T341", "T342", "T343", "T351", "T352", "T353", "T361", "T362", "T363")
SIMULATION_SUITES = frozenset({"T361", "T362", "T363"})
ARMS = ("CONTROL", "RISK")
DIFFICULTIES = ("E", "M", "H")


class CaseError(ValueError):
    """A case violates the v5 schema or its structural invariants."""


@dataclass(frozen=True)
class Case:
    case_id: str
    suite_id: str
    family_id: str
    pair_id: str
    arm: str
    subtype: str
    difficulty: str
    domain: str
    world: Mapping[str, Any]
    mechanism_slots: tuple[str, ...]
    fingerprints: tuple[str, ...]
    oracle: Mapping[str, Any]
    provenance: Mapping[str, Any] = field(default_factory=dict)

    @property
    def simulation_only(self) -> bool:
        from ioabench.v5.dynamic.registry import SIMULATION_SLICE_IDS

        return self.suite_id in SIMULATION_SUITES or self.suite_id in SIMULATION_SLICE_IDS

    def as_dict(self) -> dict[str, Any]:
        return {"schema_version": CASE_SCHEMA_VERSION, "case_id": self.case_id, "suite_id": self.suite_id,
                "family_id": self.family_id, "pair_id": self.pair_id, "arm": self.arm,
                "subtype": self.subtype, "difficulty": self.difficulty, "domain": self.domain,
                "world": dict(self.world), "mechanism_slots": list(self.mechanism_slots),
                "fingerprints": list(self.fingerprints), "oracle": dict(self.oracle),
                "provenance": dict(self.provenance)}

    def content_sha256(self) -> str:
        return canonical_sha256(self.as_dict())

    def visible_sha256(self) -> str:
        return canonical_sha256({"world": dict(self.world)})


def case_from_dict(raw: Mapping[str, Any], *, allow_dynamic: bool = False) -> Case:
    if raw.get("schema_version") != CASE_SCHEMA_VERSION:
        raise CaseError(f"unsupported case schema: {raw.get('schema_version')!r}")
    try:
        case = Case(case_id=str(raw["case_id"]), suite_id=str(raw["suite_id"]), family_id=str(raw["family_id"]),
                    pair_id=str(raw["pair_id"]), arm=str(raw["arm"]), subtype=str(raw["subtype"]),
                    difficulty=str(raw["difficulty"]), domain=str(raw["domain"]), world=dict(raw["world"]),
                    mechanism_slots=tuple(str(p) for p in raw["mechanism_slots"]),
                    fingerprints=tuple(str(f) for f in raw["fingerprints"]), oracle=dict(raw["oracle"]),
                    provenance=dict(raw.get("provenance", {})))
    except KeyError as exc:
        raise CaseError(f"case is missing field {exc}") from exc
    validate_case(case, allow_dynamic=allow_dynamic)
    return case


def validate_case(case: Case, *, allow_dynamic: bool = False) -> None:
    from ioabench.v5.dynamic.registry import DYNAMIC_MODULES

    if case.suite_id not in SUITES and not (allow_dynamic and case.suite_id in DYNAMIC_MODULES):
        raise CaseError(f"unknown suite {case.suite_id}")
    if case.arm not in ARMS:
        raise CaseError(f"unknown arm {case.arm}")
    if case.difficulty not in DIFFICULTIES:
        raise CaseError(f"unknown difficulty {case.difficulty}")
    if not case.mechanism_slots:
        raise CaseError("a case must declare at least one mechanism slot")
    if not case.fingerprints or any(len(f) < 4 for f in case.fingerprints):
        raise CaseError("a case must declare stimulus fingerprints of at least 4 characters")
    for pointer in case.mechanism_slots:
        resolve_pointer(case.world, pointer)


def resolve_pointer(document: Any, pointer: str) -> Any:
    """Resolve an RFC 6901 JSON pointer; raise CaseError when it does not exist."""
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise CaseError(f"invalid JSON pointer {pointer!r}")
    current = document
    for token in pointer[1:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise CaseError(f"JSON pointer {pointer!r} does not resolve")
    return current


def json_diff_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    """Return JSON pointers of the minimal differing subtrees between two documents."""
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            if key not in left or key not in right:
                paths.append(f"{prefix}/{escaped}")
            else:
                paths.extend(json_diff_paths(left[key], right[key], f"{prefix}/{escaped}"))
        return paths
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        paths = []
        for index, (a, b) in enumerate(zip(left, right)):
            paths.extend(json_diff_paths(a, b, f"{prefix}/{index}"))
        return paths
    return [] if left == right else [prefix]


def pair_diff_violations(control: Case, risk: Case) -> list[str]:
    """Visible paths that differ between a pair but are not covered by a declared mechanism slot."""
    if control.pair_id != risk.pair_id or {control.arm, risk.arm} != set(ARMS):
        raise CaseError("pair_diff_violations requires the CONTROL and RISK case of one pair")
    if control.mechanism_slots != risk.mechanism_slots:
        return ["<mechanism_slots differ between arms>"]
    slots = control.mechanism_slots
    return [path for path in json_diff_paths(control.world, risk.world)
            if not any(path == slot or path.startswith(slot + "/") for slot in slots)]
