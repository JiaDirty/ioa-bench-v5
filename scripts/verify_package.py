"""Verify that the editable source package imports cleanly."""

from importlib import import_module


PACKAGES = (
    "ioabench",
    "ioabench.core",
    "ioabench.models",
    "ioabench.agents",
    "ioabench.worlds",
    "ioabench.sandbox",
    "ioabench.datasets",
    "ioabench.generation",
    "ioabench.scenarios",
    "ioabench.exposures",
    "ioabench.oracle",
    "ioabench.telemetry",
    "ioabench.scoring",
    "ioabench.judges",
    "ioabench.analysis",
    "ioabench.scheduler",
    "ioabench.reports",
    "ioabench.adapters",
    "ioabench.api",
)


def main() -> int:
    for package_name in PACKAGES:
        import_module(package_name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

