from copy import deepcopy
import pytest
import yaml
from pathlib import Path
import runpy

from ioabench.v5.ai_generation.development import validate_policy, structure_vector
from ioabench.v5.ai_generation.pipeline import suite_spec
from ioabench.models.aihubmix import AIHubMixAdapter
from ioabench.v5.ai_generation import aihubmix_study


def test_development_policy_is_explicit_and_formal_claims_stay_off():
    policy = yaml.safe_load((Path(__file__).parents[2] / "config/v5/deepseek_development_policy_v1.yaml").read_text())
    assert validate_policy(policy) is policy
    for key in ("formal_accepted", "formal_scientific_claims", "same_model_audit_independent_science"):
        wrong = deepcopy(policy)
        wrong[key] = True
        with pytest.raises(ValueError):
            validate_policy(wrong)
    wrong = deepcopy(policy)
    wrong["near_duplicate_threshold"] = .99
    with pytest.raises(ValueError):
        validate_policy(wrong)


def test_mainland_endpoint_defaults_and_versioned_pilot_policies():
    endpoint = "https://api.inferera.com/v1"
    adapter = AIHubMixAdapter(api_key="test-secret", stop_on_provider_error=True)
    assert adapter.base_url == adapter.fallback_base_url == aihubmix_study.BASE_URL == endpoint
    scripts = Path(__file__).parents[2] / "scripts/v5"
    for filename, key in (("tf_ab_pilot.py", "POLICY_V12"), ("tf_r2_pilot.py", "POLICY"), ("tf_r3_pilot.py", "POLICY")):
        policy = runpy.run_path(str(scripts / filename))[key]
        assert validate_policy(policy) is policy
        assert policy["version"] == "ioabench.v5.development-policy/1.2.0"
        assert policy["base_url"] == endpoint
        legacy = {**policy, "version": "ioabench.v5.development-policy/1.1.0", "base_url": "https://aihubmix.com/v1"}
        assert validate_policy(legacy) is legacy
        with pytest.raises(ValueError):
            validate_policy({**legacy, "base_url": endpoint})
        with pytest.raises(ValueError):
            validate_policy({**policy, "formal_accepted": True})
    preflight = runpy.run_path(str(scripts / "aihubmix_preflight.py"))["preflight"]
    assert preflight.__kwdefaults__["base_url"] == endpoint


def test_structure_vector_counts_consumed_access_without_seed_or_text():
    spec = suite_spec("T333", typed=True)
    signatures = []
    for seed in (9041, 9042):
        blueprint = spec.adapter.default_blueprint(seed=seed, difficulty="M")
        control, _ = spec.adapter.compile_pair(blueprint, seed=seed)
        signatures.append(structure_vector(control)["structural_cell_sha256"])
    assert signatures[0] == signatures[1]
    blueprint["suite_payload"]["metadata_access"] = "query"
    other, _ = spec.adapter.compile_pair(blueprint, seed=9042)
    assert structure_vector(other)["structural_cell_sha256"] != signatures[0]
