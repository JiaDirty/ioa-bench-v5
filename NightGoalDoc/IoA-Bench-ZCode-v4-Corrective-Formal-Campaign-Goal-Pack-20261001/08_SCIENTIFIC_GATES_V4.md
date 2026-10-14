# Scientific Gates v4

V4-S0 Reconcile
V4-S1 Candidate Fork
V4-S2 Strict Retry Verification
V4-S3 Candidate Validation
V4-S4 Pre-freeze Scientific Audit
V4-S5 Release Freeze
V4-S6 Run Manifest Freeze
V4-S7 Provider Approval
V4-S8 Live Smoke
V4-S9 Formal Campaign
V4-S10 Post-run Validation
V4-S11 Canonical Aggregation
V4-S12 Final Delivery

关键 Gate：
- S2: INVALID terminal; INFRA_INTERRUPTED terminal; RETRYABLE only zero-behavior; attempts retained; resume idempotent
- S3: ~50 candidate checks + 19 closure + full pytest + T353 replay + baseline PASS
- S5: v4 Release frozen immutable
- S6: 18 manifests bind same release_id/release_sha256/source_tree_sha256
- S7: explicit user Provider approval
- S9: 18 suites / 1620 cases / v4 native / no cherry-pick / no rerun-to-safe
- S10: 18/18 run validation + dataset/replay/retry/SH checks
- S11: binding audit 18/18 STRICT + Phase C --final PASS
- S12: bundle/inventory/secret scan/CRC/SHA-256/state sync/final acceptance PASS
