from importlib import import_module


PACKAGE_NAMES = (
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


def test_required_packages_import() -> None:
    for package_name in PACKAGE_NAMES:
        import_module(package_name)

