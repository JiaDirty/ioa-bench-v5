"""Re-verify the frozen v4 artifacts are byte-identical (read-only).

Run after any test or mock execution to confirm the frozen v4 release,
run-manifest registry and approval artifacts were not disturbed.
"""

from __future__ import annotations

import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

EXPECTED = {
    "release/BENCHMARK_RELEASE_v4-corrective-20261001.json":
        "756194ab08c6aaad86fef973b51ffdf419b9a32898d530320fdcc2a2881b9987",
    "artifacts/scientific_closure_v4/run-manifest-registry-001.json":
        "e2e07b98f8afa7e2ea63511930f36ab3ca1962f92a6caadc9f7db6c4584d75ce",
    "artifacts/gates/V4_S4_PREFREEZE_AUDIT_001.json":
        "a79b1990e1bfbe462fc2b2eda05db012b78293fb26f82f8645813aea9ba52d28",
    "artifacts/scientific_closure_v4/provider-approval-request-001.json":
        "681458cc977187d511ad27328ca0f6fcb18e77fd3ed9282f773543f90e39b03a",
    "artifacts/gates/V4_S5_RELEASE_FREEZE_001.json":
        "fb40c2947d578d17bbeb04405199f82e17794e3d5d98101f9262854560aaedfa",
    "artifacts/gates/V4_S6_RUN_MANIFEST_FREEZE_001.json":
        "69d282558fb7c290065de43c98e66c909ecac97dccec01ac625df7bbbec73719",
}


def main() -> int:
    failed = []
    for rel, want in EXPECTED.items():
        path = ROOT / rel
        got = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "MISSING"
        ok = got == want
        print(("OK   " if ok else "DIFF "), got[:16], rel)
        if not ok:
            failed.append(rel)
    print({"checked": len(EXPECTED), "mismatched": failed, "pass": not failed})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
