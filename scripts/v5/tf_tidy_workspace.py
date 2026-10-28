"""Tidy the run directory: consolidate _tmp_* scratch into scratch/, drop caches.

Evidence bytes are preserved (moved, not deleted); ROUND_REPORT references get a
path note. The two live reaudit scripts move too and will be invoked from
scratch/ when the T321 round resumes.
"""
import shutil
from pathlib import Path

run = Path('artifacts/v5/tree_factory/tf-20261024-r1')
scratch = run / 'scratch'
scratch.mkdir(exist_ok=True)
moved_files, moved_dirs = [], []
for entry in sorted(run.iterdir()):
    if not entry.name.startswith('_tmp_'):
        continue
    target = scratch / entry.name
    if target.exists():
        continue
    shutil.move(str(entry), str(target))
    (moved_dirs if entry.is_dir() else moved_files).append(entry.name)
caches = 0
for cache in list(run.rglob('__pycache__')) + list(run.rglob('.pytest_cache')):
    shutil.rmtree(cache, ignore_errors=True)
    caches += 1
print('moved files:', len(moved_files), 'dirs:', len(moved_dirs), 'caches removed:', caches)
