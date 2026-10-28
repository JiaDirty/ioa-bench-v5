"""Measure candidate payload sizes for the review handoff (read-only)."""
import sys
from pathlib import Path

ROOT = Path('.')


def size_of(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(p.stat().st_size for p in path.rglob('*') if p.is_file())


targets = {
    'run dir (tf-20261024-r1)': ROOT / 'artifacts/v5/tree_factory/tf-20261024-r1',
    '  ├ ab/candidates': ROOT / 'artifacts/v5/tree_factory/tf-20261024-r1/ab/candidates',
    '  ├ ab/reviews': ROOT / 'artifacts/v5/tree_factory/tf-20261024-r1/ab/reviews',
    '  ├ minimal': ROOT / 'artifacts/v5/tree_factory/tf-20261024-r1/minimal',
    '  └ scratch': ROOT / 'artifacts/v5/tree_factory/tf-20261024-r1/scratch',
    'history snapshot (f1ec…)': ROOT / 'artifacts/v5/data_factory/dev_auto_audit/round-20261020/history/f1ec249532a4b1987db17c48d8172d401c1fa269cfd5d25ba77a580a1e81048b.json',
    'prior protected inventory': ROOT / 'artifacts/v5/data_factory/dev_auto_audit/round-20261020/PROTECTED_BASELINE.json',
    'dev-audit round evidence': ROOT / 'artifacts/v5/data_factory/dev_auto_audit/round-20261020',
    'goal pack': ROOT / 'docs/plans/zcode_tree_factory_20261024',
}
for name, path in targets.items():
    if not path.exists():
        sys.stdout.write('%-38s MISSING\n' % name)
        continue
    size = size_of(path)
    files = 1 if path.is_file() else sum(1 for p in path.rglob('*') if p.is_file())
    sys.stdout.write('%-38s %10.2f MB  %6d files\n' % (name, size / 1_048_576, files))
