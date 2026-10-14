"""Naturalize suite phrase templates with an independent generator model (PI-V5-002 authorized spend).

Usage: python scripts/v5/naturalize_phrasebank.py --suites T351 ... [--model glm-5.3] [--per-source 3]

For every template in a suite module's ``PHRASES`` dict ({key: [authored templates]}), the generator model is asked
for paraphrases that keep every {placeholder} exactly. Candidates are admitted only if
``ioabench.v5.phrasebank.admissible`` accepts them; rejected candidates are kept with their reasons
(AGENTS.md section 9). Output: data/v5/phrasebank/<suite>.json (an existing bank is never overwritten).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.config.loader import load_workspace_env  # noqa: E402
from ioabench.models import AIHubMixAdapter, ModelRequest  # noqa: E402
from ioabench.v5.phrasebank import BANK_DIR, PHRASEBANK_VERSION, admissible  # noqa: E402
from ioabench.v5.suites import load  # noqa: E402

# Only the formal tested model is disjoint from generator/validator roles.
ROSTER = {"deepseek-v4.1-flash"}
INSTRUCTION = (
    "Rewrite the following business text template {n} different ways for realistic workplace communication. "
    "Keep the meaning, the facts and the tone. Keep every placeholder in curly braces exactly as written (same names, "
    "each used at least once, no new placeholders). Do not add commentary. Vary sentence structure and wording. "
    "Return only a JSON array of {n} strings.\n\nTemplate:\n{template}")


def _parse(text: str) -> list[str]:
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        return []
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [v for v in value if isinstance(v, str)]


async def naturalize(suite: str, adapter: Any, profile: Any, per_source: int) -> dict[str, Any]:
    module = load(suite)
    phrases: dict[str, list[str]] = getattr(module, "PHRASES", {})
    entries: dict[str, list[dict[str, Any]]] = {}
    for key, authored in phrases.items():
        rows = entries.setdefault(key, [])
        for source in authored:
            prompt = INSTRUCTION.replace("{n}", str(per_source)).replace("{template}", source)
            response = await adapter.generate(profile, ModelRequest(
                ({"role": "user", "content": prompt},), {"temperature": 0.7, "max_tokens": 2000}))
            for candidate in _parse(response.text or ""):
                ok, reason = admissible(candidate, source)
                rows.append({"text": candidate, "source": source, "admitted": ok, "reason": reason,
                             "model": profile.model_id, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()})
    return {"suite": suite, "phrasebank_version": PHRASEBANK_VERSION, "generator_model": profile.model_id,
            "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "entries": entries,
            "admitted": sum(r["admitted"] for rows in entries.values() for r in rows),
            "rejected": sum(not r["admitted"] for rows in entries.values() for r in rows)}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suites", nargs="+", required=True)
    parser.add_argument("--model", default="glm-5.3")
    parser.add_argument("--per-source", type=int, default=3)
    args = parser.parse_args()
    if args.model in ROSTER:
        raise SystemExit("generator model must be disjoint from the tested roster")
    load_workspace_env(ROOT / ".env")
    adapter = AIHubMixAdapter()
    profile = await adapter.resolve(args.model)
    BANK_DIR.mkdir(parents=True, exist_ok=True)
    for suite in args.suites:
        target = BANK_DIR / f"{suite}.json"
        if target.exists():
            raise SystemExit(f"{target} exists; move it to a versioned name before regenerating")
        bank = await naturalize(suite, adapter, profile, args.per_source)
        target.write_text(json.dumps(bank, indent=2, ensure_ascii=False), encoding="utf-8")
        print(suite, "admitted", bank["admitted"], "rejected", bank["rejected"])


if __name__ == "__main__":
    asyncio.run(main())
