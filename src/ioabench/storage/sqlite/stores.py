"""SQLite migration and store-isolation primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import sqlite3
from pathlib import Path
from typing import Iterator, Mapping


class StoreRole(StrEnum):
    CONTROL = "control"
    ORACLE = "oracle"
    SUT = "sut"
    TELEMETRY = "telemetry"


DDL_FILES: Mapping[StoreRole, str] = {
    StoreRole.CONTROL: "001_control.sql",
    StoreRole.ORACLE: "002_oracle.sql",
    StoreRole.SUT: "003_sut.sql",
    StoreRole.TELEMETRY: "004_telemetry.sql",
}


@dataclass(frozen=True)
class LocalStores:
    paths: Mapping[StoreRole, Path]
    schema_root: Path

    @classmethod
    def from_directory(cls, data_root: str | Path, schema_root: str | Path | None = None) -> "LocalStores":
        root = Path(data_root).resolve()
        return cls(
            paths={role: root / f"{role.value}.db" for role in StoreRole},
            schema_root=Path(schema_root).resolve() if schema_root else _default_schema_root(),
        )

    def connect(self, role: StoreRole) -> sqlite3.Connection:
        path = self.paths[role]
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.execute("PRAGMA foreign_keys=ON")
        if role is StoreRole.TELEMETRY:
            connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def migrate(self) -> None:
        for role, filename in DDL_FILES.items():
            with self.connect(role) as connection:
                connection.executescript((self.schema_root / filename).read_text(encoding="utf-8"))

    def agent_visible_paths(self) -> dict[str, str]:
        return {"sut": str(self.paths[StoreRole.SUT])}

    def iter_connections(self) -> Iterator[tuple[StoreRole, sqlite3.Connection]]:
        for role in StoreRole:
            yield role, self.connect(role)


def _default_schema_root() -> Path:
    return Path(__file__).resolve().parents[4] / "contracts" / "ddl" / "sqlite"
