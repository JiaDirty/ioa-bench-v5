"""Summarize explicitly selected auxiliary-call ledgers without making provider calls."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.v5.ai_generation.auxiliary_runtime import AuxiliaryRouter
from ioabench.hashing import canonical_sha256


def _read(path, sources):
    content = path.read_bytes()
    sources[str(path.resolve())] = hashlib.sha256(content).hexdigest()
    return content.decode("utf-8-sig")


def _json(path, sources):
    return json.loads(_read(path, sources))


def _paths(roots, name):
    paths = set()
    for root in roots:
        root = Path(root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("input root must be a directory: " + str(root))
        paths.update(path.resolve() for path in root.rglob(name) if path.is_file())
    return sorted(paths, key=str)


def _tokens(usage):
    usage = usage or {}
    result = {}
    for key, alias in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens"),
                       ("total_tokens", "total_tokens")):
        value = usage.get(key, usage.get(alias))
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError("usage token count must be a nonnegative integer: " + key)
        result[key] = value
    if result["total_tokens"] is None and all(result[key] is not None for key in ("prompt_tokens", "completion_tokens")):
        result["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]
    return result


def _cost(value):
    value = value or {}
    amount = value.get("amount")
    if value.get("status") == "ESTIMATED" and value.get("currency") == "USD" and amount is not None:
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount) or amount < 0:
            raise ValueError("estimated USD amount must be finite and nonnegative")
        return {"status": "ESTIMATED", "currency": "USD", "amount": amount}
    return {"status": "UNKNOWN", "currency": "USD", "amount": None}


def _served(response):
    metadata = response.get("provider_metadata") or {}
    return ((metadata.get("transport_metadata") or {}).get("x-aihubmix-model")
            or metadata.get("model") or response.get("resolved_model_id"))


def _router_rows(ledger, sources):
    content = _read(ledger, sources)
    # Reuse the router's own hash-chain verifier without constructing a provider or writing state.
    AuxiliaryRouter.verify_ledger(SimpleNamespace(directory=ledger.parent))
    if hashlib.sha256(ledger.read_bytes()).hexdigest() != sources[str(ledger.resolve())]:
        raise ValueError("source ledger changed during verification")
    events = [json.loads(line) for line in content.splitlines() if line.strip()]
    starts, finishes = {}, {}
    for event in events:
        if event.get("event") not in {"REQUEST_STARTED", "REQUEST_FINISHED"}:
            continue
        attempt = event["attempt_id"]
        target = starts if event["event"] == "REQUEST_STARTED" else finishes
        if attempt in target:
            raise ValueError("duplicate auxiliary attempt event: " + attempt)
        target[attempt] = event
    if set(finishes) - set(starts):
        raise ValueError("auxiliary completion has no request start")
    rows = []
    for attempt, start in starts.items():
        finish = finishes.get(attempt)
        record = finish or start
        for key in ("request_id", "role", "requested_model_id", "request_sha256"):
            if finish and finish.get(key) != start.get(key):
                raise ValueError("auxiliary completion differs from its start: " + key)
        response = record.get("response") or {}
        status = record.get("status") if finish else "REQUEST_UNRESOLVED"
        if status not in {"SUCCEEDED", "FAILED", "REQUEST_UNRESOLVED"}:
            raise ValueError("unknown auxiliary attempt status: " + str(status))
        rows.append({"attempt_id": attempt, "source_kind": "ROUTER", "source_ledger": str(ledger),
            "request_directory": str(ledger.parent / start["request_id"]),
            "role": start["role"], "requested_model_id": start["requested_model_id"],
            "served_model_id": record.get("served_model_id") or _served(response),
            "response_model_id": response.get("model_id"), "status": status,
            "finished": finish is not None, "tokens": _tokens(record.get("usage") or response.get("usage")),
            "cost": _cost(record.get("cost")), "failure_category": record.get("category")})
    return rows


def _control_rows(directory, result, sources, consumed):
    rows = []
    for path in sorted(directory.rglob("EXECUTION_LOG.jsonl")):
        path = path.resolve()
        if path in consumed:
            continue
        consumed.add(path)
        events = [json.loads(line) for line in _read(path, sources).splitlines() if line.strip()]
        starts = [(index, event) for index, event in enumerate(events) if event.get("event") == "REQUEST_STARTED"]
        for ordinal, (index, start) in enumerate(starts, 1):
            role = start.get("role", "AUDITOR")
            if role not in {"AUDITOR", "GENERATOR"}:
                raise ValueError("unsupported fixed-control request role: " + str(role))
            if sum(event.get("role") == role and event.get("request_sha256") == start.get("request_sha256")
                   for _, event in starts) != 1:
                raise ValueError("repeated fixed-control request start has ambiguous response attribution")
            following = events[index + 1:]
            next_start = next((i for i, item in enumerate(following)
                               if item.get("event") == "REQUEST_STARTED" and item.get("role") == role), len(following))
            following = following[:next_start]
            failed = any(item.get("event") == "REQUEST_FAILED" and item.get("role") == role for item in following)
            request_path, response_path = path.parent / (role + "_REQUEST.json"), path.parent / (role + "_RESPONSE.json")
            request = _json(request_path, sources) if request_path.exists() else {}
            response = _json(response_path, sources) if response_path.exists() else {}
            if request and canonical_sha256(request) != start.get("request_sha256"):
                raise ValueError("control request hash differs from its actual start: " + str(request_path))
            if response and response.get("request_sha256") != start.get("request_sha256"):
                raise ValueError("control response does not match its actual request start: " + str(response_path))
            # A recorded replay has no new REQUEST_STARTED and contributes no extra attempt.
            status = "SUCCEEDED" if response else "FAILED" if failed else "REQUEST_UNRESOLVED"
            rows.append({"attempt_id": str(path.parent) + ":" + role + ":" + str(ordinal),
                "source_kind": "FIXED_CONTROL", "source_ledger": str(path),
                "request_directory": str(path.parent), "role": request.get("role") or "INDEPENDENT_AUDITOR",
                "requested_model_id": start.get("model_id") or request.get("requested_model_id") or result.get("auditor"),
                "served_model_id": _served(response), "response_model_id": response.get("model_id"),
                "status": status, "finished": bool(response) or failed,
                "tokens": _tokens(response.get("usage")), "cost": _cost(None),
                "failure_category": None})
    return rows


def _totals(rows, pools):
    costs = [row["cost"]["amount"] for row in rows if row["cost"]["status"] == "ESTIMATED"]
    costs.extend(pool["amount"] for pool in pools)
    return {"attempts_started": len(rows), "attempts_finished": sum(row["finished"] for row in rows),
        "attempts_succeeded": sum(row["status"] == "SUCCEEDED" for row in rows),
        "attempts_failed": sum(row["status"] == "FAILED" for row in rows),
        "attempts_unresolved": sum(row["status"] == "REQUEST_UNRESOLVED" for row in rows),
        "known_tokens": {key: sum(row["tokens"][key] or 0 for row in rows)
                         for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "missing_token_counts": {key: sum(row["tokens"][key] is None for row in rows)
                                 for key in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "monetary_cost": {"status": "ESTIMATED_KNOWN_SUBTOTAL", "currency": "USD", "amount": math.fsum(costs),
            "unknown_billing_attempts": sum(row["cost"]["status"] != "ESTIMATED" and not row.get("aggregate_cost_source") for row in rows),
            "aggregate_covered_attempts": sum(bool(row.get("aggregate_cost_source")) for row in rows)},
        "exact_served_model_ids": sorted({row["served_model_id"] for row in rows if row["served_model_id"]}),
        "unknown_served_identity_attempts": sum(not row["served_model_id"] for row in rows)}


def build_summary(*, router_dirs=(), control_dirs=()):
    sources, rows, pools = {}, [], []
    script = Path(__file__).resolve()
    sources[str(script)] = hashlib.sha256(script.read_bytes()).hexdigest()
    ledgers = _paths(router_dirs, "AIHUBMIX_ATTEMPTS.jsonl")
    for ledger in ledgers:
        rows.extend(_router_rows(ledger, sources))
    control_roots = {path.parent for name in ("CONTROL_RESULT.json", "CONTROL_CONTRACT.json")
                     for path in _paths(control_dirs, name)}
    consumed = set()
    for directory in sorted(control_roots, key=lambda path: (-len(path.parts), str(path))):
        if (directory / "CONTROL_CONTRACT.json").exists():
            _json(directory / "CONTROL_CONTRACT.json", sources)
        result_path = directory / "CONTROL_RESULT.json"
        result = _json(result_path, sources) if result_path.exists() else {}
        for name, expected in result.get("evidence_sha256", {}).items():
            path = (directory / name).resolve()
            if not path.is_relative_to(directory):
                raise ValueError("control evidence escapes its run directory")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValueError("control evidence hash changed: " + str(path))
            sources[str(path)] = actual
        selected = _control_rows(directory, result, sources, consumed)
        cost = _cost(result.get("monetary_cost"))
        completed = [row for row in selected if row["status"] == "SUCCEEDED"]
        identities = {(row["role"], row["requested_model_id"]) for row in completed}
        if cost["status"] == "ESTIMATED" and completed:
            if len(identities) != 1:
                raise ValueError("fixed control cost cannot be attributed to multiple model roles")
            role, model_id = next(iter(identities))
            pool = {**cost, "source": str(result_path), "role": role, "requested_model_id": model_id,
                    "request_directories": sorted({row["request_directory"] for row in completed}),
                    "basis": "CONTROL_RESULT monetary_cost; no per-request price was invented"}
            pools.append(pool)
            for row in completed:
                if all(row["tokens"][key] is not None for key in ("prompt_tokens", "completion_tokens")):
                    row["aggregate_cost_source"] = str(result_path)
        rows.extend(selected)
    groups = {}
    for field in ("role", "requested_model_id", "request_directory"):
        grouped = defaultdict(list)
        for row in rows:
            grouped[row[field]].append(row)
        groups[field] = [{field: key, **_totals(selected, [pool for pool in pools if (
            pool.get(field) == key if field != "request_directory" else False)])}
            for key, selected in sorted(grouped.items(), key=lambda item: str(item[0]))]
    if any(hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest for path, digest in sources.items()):
        raise ValueError("input evidence changed during usage summary")
    return {"schema_version": "ioabench.v5.factory-usage-summary/1", "provider_calls": 0,
        "summarizer": {"path": str(script), "sha256": sources[str(script)]},
        "counting_policy": "Router hash-chain events are authoritative. Fixed controls count actual REQUEST_STARTED records and durable responses. Wrapper GENERATOR_RESPONSE/AUDITOR_RESPONSE files outside selected fixed controls are not independently counted.",
        "totals": _totals(rows, pools), "by_role": groups["role"], "by_model": groups["requested_model_id"],
        "by_request_directory": groups["request_directory"], "attempts": rows, "aggregate_cost_pools": pools,
        "source_sha256": dict(sorted(sources.items())),
        "router_ledgers": [str(path) for path in ledgers], "fixed_control_directories": [str(path) for path in sorted(control_roots)],
        "limits": ["ESTIMATED USD is a known subtotal, not an account invoice. Failed requests and missing usage may have unknown charges.",
                   "Fixed-control cost is reported at run/role/model level; per-request cost remains unknown when not returned.",
                   "Only explicit input directories were inspected. Copied evidence in distinct paths is not assumed to be a new or duplicate paid call."]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--router-dir", type=Path, action="append", default=[])
    parser.add_argument("--control-dir", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.router_dir and not args.control_dir:
        parser.error("at least one explicit --router-dir or --control-dir is required")
    report = build_summary(router_dirs=args.router_dir, control_dirs=args.control_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"output": str(args.output.resolve()), **report["totals"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
