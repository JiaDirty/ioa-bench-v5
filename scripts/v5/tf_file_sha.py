"""Finalize the review package: FILE_SHA256.json over the loose deliverables."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

OUT = Path('exports/tree-factory-review-20261024')
deliverables = [
    'IoA-Bench-v5-TreeFactory-SOURCE-REVIEW-20261024.zip',
    'IoA-Bench-v5-TreeFactory-EVIDENCE-20261024.zip',
    'TECHNICAL_REVIEW_HANDOFF.md',
    'REVIEW_FILE_INDEX.json',
    'PACKAGE_VERIFICATION.json',
]
rows = []
for name in deliverables:
    path = OUT / name
    rows.append({"file": name, "bytes": path.stat().st_size,
                 "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
manifest = {"version": "ioabench.v5.review-file-sha/1.0.0",
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "files": rows}
(OUT / 'FILE_SHA256.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1),
                                      encoding='utf-8')
for row in rows:
    print(f"{row['bytes']:>10,}  {row['sha256'][:16]}…  {row['file']}")
