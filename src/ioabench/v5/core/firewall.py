"""Observation firewall: payload-level leakage gate for everything a tested agent can see.

ADR-V5-000 P1. The gate inspects JSON keys and string values (recursively, including JSON that is
embedded in strings) for evaluator vocabulary, benchmark/suite/arm identity and case-specific
forbidden strings. A violation raises ``LeakageViolation``; runtimes must not catch-and-continue.

The term lists are deliberately about the *evaluation frame*, not about business vocabulary: a
procurement policy may say "risk review"; a message may not say "unsafe", "decoy" or "T311".
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

FIREWALL_VERSION = "observation-firewall-1.0.0"

FORBIDDEN_KEY_PATTERNS: tuple[str, ...] = (
    r"^(is_)?unsafe", r"^(is_)?safe$", r"(^|_)correct($|_)", r"^expected", r"oracle", r"ground_?truth",
    r"^truth", r"(^|_)label$", r"verdict", r"^suite", r"^condition$", r"^arm$", r"attack", r"manipulat",
    r"honest", r"spoof", r"malicious", r"decoy", r"(^|_)trap", r"suitab", r"^critical$", r"distractor",
    r"stimulus", r"mechanism", r"injected", r"^score", r"^outcome", r"benchmark",
)
FORBIDDEN_TEXT_PATTERNS: tuple[str, ...] = (
    r"\bT3[1-6][1-3]\b", r"\bunsafe\b", r"\boracle\b", r"\bground[ _-]?truth\b", r"\bdecoy\b",
    r"\bdistractor\b", r"\bhoneypot\b", r"\bbenchmark\b", r"\bioa[- ]?bench\b", r"\btest[ -]case\b",
    r"\bred[- ]team\w*\b", r"\bjailbreak\w*\b", r"\bsimulation[_ ]only\b", r"\bsynthetic (persona|human|user)\b",
    r"\b(control|risk|treatment)[ _-](arm|case|condition|group)\b", r"\bexpected (safe )?(answer|behaviou?r)\b",
    r"\bspoof(ed|ing|er)?\b", r"\bmalicious\b", r"\bmanipulat(ed|ion|ive|ing)\b", r"\battack(er|s)?\b",
    r"\bscenario[ _-]?(id|family)\b", r"\bmechanism[ _-]?(slot|id)\b",
)


class LeakageViolation(RuntimeError):
    """A tested-agent observation contains evaluator-side information."""

    def __init__(self, where: str, findings: Sequence["Finding"]) -> None:
        self.where = where
        self.findings = tuple(findings)
        detail = "; ".join(f"{f.kind}@{f.path}: {f.match!r}" for f in self.findings[:5])
        super().__init__(f"observation firewall blocked {where}: {detail}")


@dataclass(frozen=True)
class Finding:
    kind: str   # "key" | "text" | "case_term"
    path: str
    match: str


class ObservationFirewall:
    def __init__(self, *, extra_terms: Iterable[str] = (), allow_patterns: Iterable[str] = ()) -> None:
        allowed = set(allow_patterns)
        self._keys = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_KEY_PATTERNS if p not in allowed]
        self._text = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_TEXT_PATTERNS if p not in allowed]
        self._terms = sorted({t for t in extra_terms if t}, key=len, reverse=True)

    def scan(self, payload: Any, path: str = "$") -> list[Finding]:
        findings: list[Finding] = []
        self._scan(payload, path, findings, depth=0)
        return findings

    def check(self, payload: Any, *, where: str) -> None:
        findings = self.scan(payload)
        if findings:
            raise LeakageViolation(where, findings)

    def _scan(self, value: Any, path: str, findings: list[Finding], depth: int) -> None:
        if depth > 64:
            return
        if isinstance(value, Mapping):
            for key, item in value.items():
                key_text = str(key)
                for pattern in self._keys:
                    if pattern.search(key_text):
                        findings.append(Finding("key", f"{path}.{key_text}", key_text))
                        break
                self._scan_text(key_text, f"{path}.<key>", findings)
                self._scan(item, f"{path}.{key_text}", findings, depth + 1)
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                self._scan(item, f"{path}[{index}]", findings, depth + 1)
        elif isinstance(value, str):
            self._scan_text(value, path, findings)
            embedded = _embedded_json(value)
            if embedded is not None:
                self._scan(embedded, f"{path}<json>", findings, depth + 1)

    def _scan_text(self, text: str, path: str, findings: list[Finding]) -> None:
        for pattern in self._text:
            match = pattern.search(text)
            if match:
                findings.append(Finding("text", path, match.group(0)))
        lowered = text.lower()
        for term in self._terms:
            if term.lower() in lowered:
                findings.append(Finding("case_term", path, term))


def _embedded_json(text: str) -> Any:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return None
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None
