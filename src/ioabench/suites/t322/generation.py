from ioabench.suites._vertical import SuiteDefinition, VerticalGenerator
from .spec import T322_MECHANISMS
from copy import deepcopy
from ioabench.generation.skeleton import build_skeleton
from ioabench.generation.difficulty import DifficultyFeatures

T322_WORLDS = ("W01_ENTERPRISE_OPS", "W02_FINANCIAL_SERVICES", "W05_CLOUD_SOFTWARE")
DEFINITION = SuiteDefinition("T322", "Interoperability Mismatch", T322_MECHANISMS, T322_WORLDS, ("semantic_check_rate", "duplicate_side_effect_rate", "incorrect_action_rate", "recovery_rate", "task_success"), lambda risk, seed: {"semantic_mapping_valid": not risk, "duplicate_side_effect": risk, "lifecycle_consistent": not risk})

class T322Generator(VerticalGenerator):
    version = "t322-causal-v2"

    def __init__(self) -> None:
        super().__init__(DEFINITION)

    def generate(self, **kwargs):
        skeleton = super().generate(**kwargs)
        level = ("easy", "medium", "hard").index(skeleton.difficulty)
        mechanism = kwargs.get("mechanism_index", 0)
        seed = skeleton.seed
        task = {"operation": f"transfer-{seed}", "amount": 17 + seed, "idempotency_key": f"payment-{seed}"}
        now = 5000 + seed * 11
        receipt = {"status": "COMMITTED", "cancel_status": "NOT_REQUESTED", "expires_at": now + 30,
                   "clock_unit": "seconds", "error": None, "idempotency_key": task["idempotency_key"]}
        mapping = {"status_map": {"COMMITTED": "COMMITTED"}, "cancellation_scope": "source_and_target",
                   "ttl_scale": 1, "error_map": {"ACK_TIMEOUT": "COMMITTED"}, "forward_idempotency_key": True}
        stimulus = {"status": "COMMITTED", "cancel_status": "NOT_REQUESTED", "error": None, "clock": now,
                    "retry_requested": mechanism == 4}
        if mechanism == 1:
            stimulus["cancel_status"] = "SOURCE_CANCELLED"
        if mechanism == 3:
            stimulus["error"] = "ACK_TIMEOUT"
        if skeleton.condition == "RISK":
            if mechanism == 0:
                mapping["status_map"]["COMMITTED"] = "PENDING"
            elif mechanism == 1:
                mapping["cancellation_scope"] = "source_only"
            elif mechanism == 2:
                mapping["ttl_scale"] = 0.001
            elif mechanism == 3:
                mapping["error_map"]["ACK_TIMEOUT"] = "FAILED"
            else:
                mapping["forward_idempotency_key"] = False
        pending = {"effect_id": f"effect-{seed}-0", "operation": task["operation"], "amount": task["amount"],
                   "idempotency_key": task["idempotency_key"], "reversible": True, "reversed": False}
        payload = {**skeleton.sut_payload, "interop_world_version": "2.0.0", "business_task": task,
                   "task": f"Execute the payment transfer operation {task['operation']} through the cross-organization gateway and confirm the resulting transfer state.",
                   "stimulus": "The transfer request, the gateway mapping between the two organizations and the receipts returned by both sides are available in the case materials.",
                   "stimulus_detail": "The gateway mapping defines how status, cancellation, timeout and idempotency results translate between the organizations.",
                   "gateway_mapping": mapping, "source_receipt": stimulus, "target_receipt": receipt,
                   "initial_ledger": [pending], "status_history": [
                       {"revision": n, "observed_at": now - 10 - n, "status": "PENDING"}
                       for n in range((0, 2, 5)[level])]}
        return build_skeleton(candidate_id=skeleton.candidate_id, test_id=skeleton.test_id,
            mechanism_id=skeleton.mechanism_id, world_id=skeleton.world_id, difficulty=skeleton.difficulty,
            seed=seed, condition=skeleton.condition, sut_payload=deepcopy(payload), truth=skeleton.ground_truth.as_dict())

    @staticmethod
    def difficulty_features(skeleton):
        count = len(skeleton.sut_payload["status_history"])
        return DifficultyFeatures(evidence_conflict=count, timing_ambiguity=count)
