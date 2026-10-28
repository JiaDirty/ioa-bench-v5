"""Only bound engineering generator profiles load; auditor privileges are never inherited."""
import hashlib
import json

import pytest

from ioabench.runtime.full_manifest import source_tree_hash
from ioabench.v5.ai_generation.auxiliary_runtime import engineering_contracts


def fixture_profile(root):
    model = "mimo-v2.6-pro"
    score = {"config_id": "mimo--enabled", "R_pass": 8, "Q_completed": 8,
        "engineering_nonduplicate_valid_pairs": 4,
        "parameter_binding": {"model": model, "protocol": "openai.chat_completions",
                              "parameters": {"max_completion_tokens": 4096}}}
    values = {"SCORECARD_ALL_MODELS.json": [score], "MODEL_CATALOG.json": [{"model_id": model, "vendor": "xiaomi"}],
              "BENCHMARK_TASKSET_FROZEN.json": {"auditor_qualified": False}}
    for name, value in values.items():
        (root / name).write_text(json.dumps(value), encoding="utf-8")
    payload = {"version": "ioabench.v5.engineering-routing-profile/1", "source_sha256": source_tree_hash(root),
        "base_url": "https://api.inferera.com/v1", "evidence_sha256": {
            name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in values},
        "contracts": [{"recommended_role": "MAIN_GENERATOR", "config_id": "mimo--enabled", "contract": {
            "profile": {"provider": "aihubmix", "model_id": model,
                        "capabilities": {"endpoint_family": "openai.chat_completions"}},
            "parameters": {"max_completion_tokens": 16384}, "allowed_roles": ["INDEPENDENT_AUDITOR"]}}]}
    path = root / "AUXILIARY_ROUTING_PROFILE.json"
    path.write_text(json.dumps(payload))
    return path, payload


def test_verified_profile_loads_only_generator_privileges(tmp_path):
    path, _ = fixture_profile(tmp_path)
    catalog, contracts, endpoint = engineering_contracts(path, workspace=tmp_path, model_ids=["mimo-v2.6-pro"])
    assert endpoint == "https://api.inferera.com/v1" and len(contracts) == 1
    assert contracts[0].allowed_roles == ("GENERATOR",) and contracts[0].judge_gold_evidence is None
    assert contracts[0].parameters == {"max_completion_tokens": 16384}


@pytest.mark.parametrize("change", ["source", "evidence", "parameters", "endpoint", "unmeasured"])
def test_modified_or_incomplete_profiles_fail_closed(tmp_path, change):
    path, payload = fixture_profile(tmp_path)
    if change == "source":
        payload["source_sha256"] = "wrong"
    elif change == "evidence":
        (tmp_path / "MODEL_CATALOG.json").write_text("[]")
    elif change == "parameters":
        payload["contracts"][0]["contract"]["parameters"]["max_completion_tokens"] = 4096
    elif change == "endpoint":
        payload["base_url"] = "https://unverified.invalid/v1"
    elif change == "unmeasured":
        payload["contracts"][0]["config_id"] = "other"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        engineering_contracts(path, workspace=tmp_path, model_ids=["mimo-v2.6-pro"])
