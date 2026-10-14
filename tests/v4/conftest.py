"""V4 tests target a separate source tree and must run in their own pytest process.

The active v4.1.7 strict-retry behaviour lives in
`artifacts/scientific_closure_v4/corrective-candidate-v11`. A single pytest
process cannot hold both that snapshot and the editable workspace package, so:

  * workspace suites  ->  python -B -X utf8 -m pytest tests --ignore=tests/v4 -q
  * v4 candidate      ->  python -B -X utf8 -m pytest tests/v4 -q

This conftest makes the v4 run self-sufficient and makes an accidental combined
run fail loudly instead of silently testing the wrong tree.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
CANDIDATE_SRC = (ROOT / "artifacts/scientific_closure_v4/corrective-candidate-v11/src").resolve()
WORKSPACE_SRC = (ROOT / "src").resolve()


def _install_candidate() -> bool:
    if not (CANDIDATE_SRC / "ioabench").is_dir():
        return False
    for name in [n for n in list(sys.modules) if n == "ioabench" or n.startswith("ioabench.")]:
        origin = getattr(sys.modules.get(name), "__file__", None)
        if origin is None or not Path(origin).resolve().is_relative_to(CANDIDATE_SRC):
            del sys.modules[name]
    for entry in list(sys.path):
        try:
            resolved = str(Path(entry or ".").resolve())
        except (OSError, ValueError):
            continue
        if resolved in (str(CANDIDATE_SRC), str(WORKSPACE_SRC)):
            sys.path.remove(entry)
    sys.path.insert(0, str(CANDIDATE_SRC))
    return True


_install_candidate()
