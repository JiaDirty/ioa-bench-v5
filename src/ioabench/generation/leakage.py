"""Oracle-label and hidden-truth leakage detection for visible payloads."""

from __future__ import annotations

from typing import Any, Mapping


HIDDEN_KEYS = frozenset({"oracle", "oracle_ref", "oracle_payload", "ground_truth", "hidden_truth", "truth", "truth_label", "attack_label", "scoring_rules"})
PROMPT_LEAKAGE_TERMS = (
    "should be checked", "must be checked", "verify before", "must verify", "should verify",
    "safe behavior", "unsafe behavior", "risk case", "attack case", "benchmark case",
)


def find_leaks(visible: Any, hidden: Any) -> tuple[str, ...]:
    leaks: list[str] = []
    _walk_keys(visible, "", leaks)
    hidden_values = {str(value).casefold() for value in _scalar_values(hidden) if str(value)}
    for value in _scalar_values(visible):
        # Public protocol booleans and absent fields are not hidden verdict labels.
        # Explicit hidden keys and textual verdict copies remain forbidden.
        if value is None or isinstance(value, bool):
            continue
        if str(value).casefold() in hidden_values and len(str(value)) > 3:
            leaks.append(f"hidden-value:{value}")
    return tuple(dict.fromkeys(leaks))


def has_leak(visible: Any, hidden: Any) -> bool:
    return bool(find_leaks(visible, hidden))


def find_prompt_leaks(visible: Any) -> tuple[str, ...]:
    leaks: list[str] = []
    for value in _scalar_values(visible):
        text = str(value).casefold()
        leaks.extend(term for term in PROMPT_LEAKAGE_TERMS if term in text)
    return tuple(dict.fromkeys(leaks))


def _walk_keys(value: Any, path: str, leaks: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if str(key).casefold() in HIDDEN_KEYS:
                leaks.append(f"hidden-key:{next_path}")
            _walk_keys(item, next_path, leaks)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _walk_keys(item, f"{path}[{index}]", leaks)


def _scalar_values(value: Any) -> list[Any]:
    if isinstance(value, Mapping):
        return [item for child in value.values() for item in _scalar_values(child)]
    if isinstance(value, (list, tuple)):
        return [item for child in value for item in _scalar_values(child)]
    return [value]
