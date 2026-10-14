"""Selective integration of the Codex AI data-factory snapshot (post-audit P3, PI option A).

Ported per the snapshot HANDOFF.md reuse boundary:
  * blueprint_schema — Blueprint JSON Schema validation (Draft 2020-12);
  * validator — independent reviewer output contract (fail-closed verdict rules);
  * suite_adapter — the GeneratedSuiteAdapter Protocol for suite compilers;
  * blueprint data — the canonical Blueprint JSON Schema document.

NOT ported (legacy, per HANDOFF): t321_adapter.py compile_pair (old fixed Case/world shape —
must not become the dynamic-world capability ceiling), diversity.py (superseded by ZCode's
executable_structure_signature + family_registry), provider requester wiring.

The dynamic blueprint compiler lives in t321_dyna_compiler.py and targets the ZCode-authoritative
dynamic world (T321-DYNA structure in t321_slice.py) with fail-closed CAPABILITY_GAP fidelity.
"""
from pathlib import Path

from .blueprint_schema import load_schema, validate_blueprint
from .suite_adapter import GeneratedSuiteAdapter
from .pipeline import CandidateRejected, SuitePipelineSpec, compile_and_gate, run_reference_policies
from .validator import REVIEW_DIMENSIONS, validate_review

BLUEPRINT_SCHEMA_DATA = Path(__file__).resolve().parent / "data" / "02_BLUEPRINT_SCHEMA.json"

__all__ = ["BLUEPRINT_SCHEMA_DATA", "CandidateRejected", "GeneratedSuiteAdapter", "REVIEW_DIMENSIONS",
           "SuitePipelineSpec", "compile_and_gate", "run_reference_policies",
           "load_schema", "validate_blueprint", "validate_review"]
