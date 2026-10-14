"""Load local-v1 configuration without persisting secrets."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

import yaml

from ioabench.errors import ConfigurationError


@dataclass(frozen=True)
class BenchmarkConfig:
    profile: str
    provider: str
    tested_model: str
    repetitions: int
    public_internet: bool
    docker_required: bool
    storage: dict[str, Path]
    artifacts_root: Path
    reports_root: Path
    datasets_root: Path

    @classmethod
    def load(cls, path: str | Path) -> "BenchmarkConfig":
        config_path = Path(path).resolve()
        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise ConfigurationError(f"cannot read configuration: {config_path}") from exc
        if not isinstance(raw, dict):
            raise ConfigurationError("configuration root must be a mapping")
        if raw.get("profile") != "local-v1":
            raise ConfigurationError("only the local-v1 profile is supported")
        if raw.get("public_internet") is not False:
            raise ConfigurationError("local-v1 requires public_internet=false")
        if raw.get("docker_required") is not False:
            raise ConfigurationError("local-v1 does not require Docker")
        project_root = config_path.parent.parent
        storage = raw.get("storage")
        if not isinstance(storage, dict):
            raise ConfigurationError("storage must be a mapping")
        storage_paths = {
            str(name): _resolve(project_root, value)
            for name, value in storage.items()
        }
        return cls(
            profile=str(raw["profile"]),
            provider=str(raw["provider"]),
            tested_model=str(raw["tested_model"]),
            repetitions=int(raw["repetitions"]),
            public_internet=False,
            docker_required=False,
            storage=storage_paths,
            artifacts_root=_resolve(project_root, raw["artifacts_root"]),
            reports_root=_resolve(project_root, raw["reports_root"]),
            datasets_root=_resolve(project_root, raw["datasets_root"]),
        )

    def safe_dict(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "provider": self.provider,
            "tested_model": self.tested_model,
            "repetitions": self.repetitions,
            "public_internet": self.public_internet,
            "docker_required": self.docker_required,
            "storage": {name: str(path) for name, path in self.storage.items()},
            "artifacts_root": str(self.artifacts_root),
            "reports_root": str(self.reports_root),
            "datasets_root": str(self.datasets_root),
        }


@dataclass(frozen=True, repr=False)
class SecretStore:
    _values: Mapping[str, str]

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "SecretStore":
        source = os.environ if environ is None else environ
        values = {name: value for name, value in source.items() if name.endswith("_API_KEY") and value}
        return cls(values)

    def get(self, name: str) -> str | None:
        return self._values.get(name)

    def redact(self, text: str) -> str:
        redacted = text
        for value in self._values.values():
            redacted = redacted.replace(value, "[REDACTED_SECRET]")
        return redacted

    def __repr__(self) -> str:
        return "SecretStore(<redacted>)"


def load_workspace_env(path: str | Path = ".env") -> None:
    """Populate the process environment from the workspace .env file.

    This is the local-secret bridge sanctioned by M0-002: keys placed in the
    workspace .env (per .env.example) become available through os.environ for
    adapters that read the environment.  Values are never logged.  Existing
    environment entries always win.
    """
    env_path = Path(path)
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if name and value and name not in os.environ:
            os.environ[name] = value


def load_settings(path: str | Path, environ: Mapping[str, str] | None = None) -> tuple[BenchmarkConfig, SecretStore]:
    return BenchmarkConfig.load(path), SecretStore.from_environment(environ)


def _resolve(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value:
        raise ConfigurationError("configured path must be a non-empty string")
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
