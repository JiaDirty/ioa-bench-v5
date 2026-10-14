"""Align PROJECT_STATE in_progress/next with the repository's convention.

The state-consistency test requires `next` to be a subset of `in_progress`:
whatever is queued next is, by definition, the work currently open. The v4 sync
had put the approval gate in `in_progress` and the provider phases in `next`.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path("D:/Project/ioa_codex_spec")
STATE = ROOT / "state/PROJECT_STATE.yaml"

state = yaml.safe_load(STATE.read_text(encoding="utf-8"))
in_progress = ["V4-S7-PROVIDER-APPROVAL"]
state["in_progress"] = in_progress
state["next"] = ["V4-S7-PROVIDER-APPROVAL"]
state["next_task"] = "V4-S7-PROVIDER-APPROVAL"
state["blocked_external"] = ("explicit user approval required for AIHubMix live smoke (V4-S8) and the "
                             "18-suite formal campaign (V4-S9); v4 release and manifests are frozen")
STATE.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")
print({"in_progress": in_progress, "next": state["next"], "next_task": state["next_task"]})
