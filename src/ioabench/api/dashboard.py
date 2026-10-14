"""Read-only dashboard payload and local HTTP server."""

from __future__ import annotations

import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ioabench.analysis.metrics import analyze_run


CATEGORIES = {
    "trust_authorization": ("T311", "T312", "T313"),
    "protocol_interop": ("T321", "T322", "T323"),
    "propagation_inference": ("T331", "T332", "T333"),
    "public_knowledge": ("T341", "T342", "T343"),
    "ecosystem_power": ("T351", "T352", "T353"),
    "human_agency_simulation": ("T361", "T362", "T363"),
}


def dashboard_payload(root: str | Path, run_id: str) -> dict[str, Any]:
    root = Path(root)
    summary = analyze_run(root, run_id)
    selected_path = root / "data" / "reports" / run_id / "case-studies" / "selected.json"
    case_studies = json.loads(selected_path.read_text(encoding="utf-8")) if selected_path.exists() else []
    return {"run_id": run_id, "categories": {name: {suite: summary["suites"].get(suite) for suite in suites} for name, suites in CATEGORIES.items()}, "status_counts": summary["status_counts"], "case_studies": case_studies}


def dashboard_html(payload: dict[str, Any]) -> str:
    rows = []
    for category, suites in CATEGORIES.items():
        for suite in suites:
            value = payload["categories"][category][suite]
            if value is None:
                rows.append(f"<tr><td>{suite}</td><td>{category}</td><td colspan='4'>not available</td></tr>")
                continue
            details = escape(json.dumps({"safety_metrics": value.get("safety_metrics", {}), "breakdowns": value.get("breakdowns", {})}, ensure_ascii=False, sort_keys=True))
            utility = value.get("task_utility", {}).get("task_success")
            rows.append(f"<tr><td>{suite}</td><td>{category}</td><td>{value.get('valid_count', 0)}/{value.get('case_count', 0)}</td><td>{escape(str(utility))}</td><td>{value.get('validity')}</td><td><details><summary>details</summary><pre>{details}</pre></details></td><td></td></tr>")
    case_links = "".join(f"<li><a href='/replay/{escape(str(item.get('replay', '')).replace('\\', '/').rsplit('/', 1)[-1].removesuffix('.json'))}'>{escape(str(item.get('kind')))} {escape(str(item.get('suite')))} {escape(str(item.get('case_id')))}</a></li>" for item in payload.get("case_studies", []))
    return (f"<!doctype html><meta charset='utf-8'><title>IoA-Bench {escape(str(payload['run_id']))}</title>"
            f"<h1>IoA-Bench {escape(str(payload['run_id']))}</h1><p>Safety and Task Utility remain separate. No overall 18-suite score. "
            f"T361–T363 are <strong>SIMULATION_ONLY</strong>.</p><p>Status: {escape(json.dumps(payload.get('status_counts', {}), sort_keys=True))} | <a href='/api'>JSON API</a></p>"
            f"<table><tr><th>Suite</th><th>Category</th><th>Valid/Cases</th><th>Task Utility</th><th>Validity</th><th>Safety and breakdowns</th><th>Replay</th></tr>{''.join(rows)}</table>"
            f"<h2>Representative replay cases</h2><ul>{case_links or '<li>none selected</li>'}</ul>")


def serve_dashboard(root: str | Path, run_id: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    root = Path(root)
    payload = dashboard_payload(root, run_id)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api":
                content_type = "application/json; charset=utf-8"
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            elif self.path.startswith("/replay/"):
                work_id = self.path.removeprefix("/replay/").replace("/", "")
                replay = root / "data" / "runs" / run_id / "replay" / f"{work_id}.json"
                if not replay.is_file():
                    self.send_error(404)
                    return
                content_type = "application/json; charset=utf-8"
                body = replay.read_bytes()
            else:
                content_type = "text/html; charset=utf-8"
                body = dashboard_html(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: Any) -> None:
            return

    ThreadingHTTPServer((host, port), Handler).serve_forever()
