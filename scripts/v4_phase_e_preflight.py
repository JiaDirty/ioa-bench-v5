"""Phase E pre-flight: orchestrator env bridging + frozen version alignment (read-only)."""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

report: dict = {"artifact": "V4_PHASE_E_PREFLIGHT", "provider_calls": 0}

# ---- 1. does the orchestrator load .env for its children? ----
orch = (ROOT / "scripts/run_online_campaign.py").read_text(encoding="utf-8")
report["orchestrator_loads_dotenv"] = bool(re.search(r"load_workspace_env|load_dotenv", orch))
report["orchestrator_child_env"] = re.search(r"environment = \{.*\}", orch).group(0)

# ---- 2. does the child CLI or adapter load .env? ----
cli = (ROOT / "src/ioabench/cli.py").read_text(encoding="utf-8")
adapter = (ROOT / "src/ioabench/models/aihubmix.py").read_text(encoding="utf-8")
report["cli_loads_dotenv"] = bool(re.search(r"load_workspace_env|load_dotenv", cli))
report["adapter_loads_dotenv"] = bool(re.search(r"load_workspace_env|load_dotenv", adapter))
report["adapter_key_source"] = "os.environ.get(\"AIHUBMIX_API_KEY\")" in adapter

# ---- 3. frozen version map vs the frozen v4 manifests ----
from ioabench.frozen_versions import FROZEN_VERSIONS  # noqa: E402

manifest_dir = ROOT / "data/runs/_v4_manifests"
mismatches = []
for path in sorted(manifest_dir.glob("*.manifest.json")):
    m = json.loads(path.read_text(encoding="utf-8"))
    suite, ver = next(iter(m["benchmark"]["suite_versions"].items()))
    want = m["benchmark"]["dataset_versions"][suite]
    have = FROZEN_VERSIONS.get(suite)
    if have != want or ver != want:
        mismatches.append({"suite": suite, "manifest": want, "frozen_versions": have})

report["frozen_versions_match_v4_manifests"] = not mismatches
report["frozen_version_mismatches"] = mismatches
report["frozen_versions"] = dict(sorted(FROZEN_VERSIONS.items()))

# ---- 4. run id the orchestrator will produce vs the frozen manifest run ids ----
orch_run_ids = {}
for suite in FROZEN_VERSIONS:
    orch_run_ids[suite] = f"deepseek-v4.1-flash-{suite}-{FROZEN_VERSIONS[suite]}-v4-formal"
manifest_run_ids = {}
for path in sorted(manifest_dir.glob("*.manifest.json")):
    m = json.loads(path.read_text(encoding="utf-8"))
    suite = next(iter(m["benchmark"]["suite_versions"]))
    manifest_run_ids[suite] = m["run_id"]
report["run_id_alignment"] = {
    s: {"orchestrator": orch_run_ids.get(s), "manifest": manifest_run_ids.get(s),
        "match": orch_run_ids.get(s) == manifest_run_ids.get(s)}
    for s in sorted(manifest_run_ids)
}
report["run_id_all_match"] = all(v["match"] for v in report["run_id_alignment"].values())

# ---- 5. provider denominator / concurrency consistency ----
report["orchestrator_concurrency"] = "IOABENCH_CONCURRENCY" in orch and '"3"' in orch

out = ROOT / "artifacts/scientific_closure_v4/phase-e-preflight-001.json"
out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

summary = {k: v for k, v in report.items() if k not in ("frozen_versions", "run_id_alignment")}
print(json.dumps(summary, ensure_ascii=False, indent=2))
