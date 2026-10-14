from ioabench.generation.prompts import NATURALIZATION_V1
from ioabench.generation.provenance import record_provenance


def test_generation_provenance_records_version_model_settings_parents_and_hashes() -> None:
    prompt = NATURALIZATION_V1.render({"role": "executor", "task": "review invoice"})
    provenance = record_provenance(
        artifact_id="candidate-1", prompt_template_id=NATURALIZATION_V1.template_id,
        prompt_version=NATURALIZATION_V1.version, model_id="generator-model",
        settings={"temperature": 0.2}, parents=("skeleton-1",), prompt=prompt, output="description",
    )
    value = provenance.as_dict()
    assert value["prompt_version"] == "1.0.0"
    assert value["model_id"] == "generator-model"
    assert value["parent_ids"] == ("skeleton-1",)
    assert len(value["input_sha256"]) == 64
    assert len(value["output_sha256"]) == 64
