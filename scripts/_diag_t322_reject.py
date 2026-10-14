"""Pull T322 2.4.0 rejection evidence and campaign progress."""
import json
from pathlib import Path

cache = Path("data/datasets/T322/2.4.0/semantic-validation-cache.json")
data = json.loads(cache.read_text(encoding="utf-8"))
found = False
for item in data.get("results", []):
    if not item.get("accepted"):
        found = True
        print("candidate:", item.get("candidate_id"), "| accepted:", item.get("accepted"))
        for verdict in item.get("verdicts", []):
            print(f"  {verdict.get('validator_id')}: {verdict.get('label')} (conf {verdict.get('confidence')})")
            for ref in verdict.get("evidence_refs", [])[:6]:
                print(f"     - {ref}")
        break
if not found:
    print("no rejected entries found in cache (all 90 accepted in cache)")

s = json.load(open("artifacts/gates/ONLINE_CAMPAIGN_STATE.json", encoding="utf-8"))
print()
print("formal complete:", [suite for suite, e in s["suites"].items() if e.get("formal_complete")])
print("campaign_complete:", s.get("campaign_complete"))
for suite in ("T322", "T323", "T331", "T332", "T333", "T341", "T342", "T343"):
    e = s["suites"].get(suite, {})
    if e:
        print(f"{suite} | pilot exit: {e.get('pilot', {}).get('exit')} | formal_complete: {e.get('formal_complete')} | blocked: {e.get('blocked')}")
