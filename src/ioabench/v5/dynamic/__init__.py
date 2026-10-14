"""Dynamic-world vertical slices (experimental engineering namespace).

These modules prove the dynamic runtime on real constructs without touching the frozen
18-suite modules (`ioabench.v5.suites.*`), their scorers or their datasets. Slices carry their
own scenario/scorer/policy versions and are validation targets for the M4 gate — they are NOT
formal datasets and never enter pilot or campaign denominators.
"""
