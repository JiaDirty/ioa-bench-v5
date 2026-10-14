from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_v4_1_campaign_uses_global_release_bound_smoke():
    campaign = (ROOT / "scripts/run_online_campaign.py").read_text(encoding="utf-8")
    assert "ONLINE_CAMPAIGN_STATE_v4_1_7.json" in campaign
    assert "V4_1_7_S8_LIVE_SMOKE.json" in campaign
    assert "verify_live_smoke(release)" in campaign
    assert "run_online_pilot.py" not in campaign


def test_historical_pilot_remains_separate_from_v4_1_campaign():
    campaign = (ROOT / "scripts/run_online_campaign.py").read_text(encoding="utf-8")
    pilot = (ROOT / "scripts/run_online_pilot.py").read_text(encoding="utf-8")
    assert "run_online_pilot.py" not in campaign
    assert 'parser.add_argument("--v4", action="store_true"' in pilot
    assert "v4=args.v4" in pilot
