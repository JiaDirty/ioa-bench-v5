"""Exact opt-in registry for the versioned dynamic adapters; classic suites stay separate."""
from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from ioabench.v5.core.case import Case

DYNAMIC_MODULES = {
    "T311-DYNA": "ioabench.v5.dynamic.t311_slice",
    "T312-DYNA": "ioabench.v5.dynamic.t312_slice",
    "T313-DYNA": "ioabench.v5.dynamic.t313_slice",
    "T321-DYNA": "ioabench.v5.dynamic.t321_slice",
    "T321-DYNB": "ioabench.v5.dynamic.t321_slice_b",
    "T322-DYNA": "ioabench.v5.dynamic.t322_slice",
    "T323-DYNA": "ioabench.v5.dynamic.t323_slice",
    "T331-DYNA": "ioabench.v5.dynamic.t331_slice",
    "T332-DYNA": "ioabench.v5.dynamic.t332_slice",
    "T333-DYNA": "ioabench.v5.dynamic.t333_slice",
    "T341-DYNA": "ioabench.v5.dynamic.t341_slice",
    "T342-DYNA": "ioabench.v5.dynamic.t342_slice",
    "T343-DYNA": "ioabench.v5.dynamic.t343_slice",
    "T351-DYNA": "ioabench.v5.dynamic.t351_slice",
    "T352-DYNA": "ioabench.v5.dynamic.t352_slice",
    "T353-DYNA": "ioabench.v5.dynamic.t353_slice",
    "T361-DYNA": "ioabench.v5.dynamic.t361_slice",
    "T362-DYNA": "ioabench.v5.dynamic.t362_slice",
    "T363-DYNA": "ioabench.v5.dynamic.t363_slice",
}
SIMULATION_SLICE_IDS = frozenset({"T361-DYNA", "T362-DYNA", "T363-DYNA"})


def implemented() -> list[str]:
    return list(DYNAMIC_MODULES)


def get_adapter(suite_id: str) -> ModuleType:
    if suite_id not in DYNAMIC_MODULES:
        raise KeyError(f"unknown dynamic suite {suite_id}")
    module = importlib.import_module(DYNAMIC_MODULES[suite_id])
    if module.SLICE_ID != suite_id:
        raise ValueError(f"dynamic adapter identity mismatch for {suite_id}")
    return module


def load_case(raw: Mapping[str, Any]) -> Case:
    from ioabench.v5.core.case import CaseError, case_from_dict

    if raw.get("suite_id") not in DYNAMIC_MODULES:
        raise CaseError(f"unknown dynamic suite {raw.get('suite_id')}")
    return case_from_dict(raw, allow_dynamic=True)
