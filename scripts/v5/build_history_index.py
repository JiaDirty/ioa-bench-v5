"""Reproducible, immutable index of on-disk v5 experimental case history. API calls: zero."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ioabench.hashing import canonical_sha256
from ioabench.v5.ai_generation.history import _cases, build_index, discover_sources, verify_sources
from ioabench.v5.core.case import CASE_SCHEMA_VERSION, case_from_dict
from ioabench.v5.evaluation import atomic_json


def case_members(archive, *, archive_name, findings, prefix="", depth=0):
    for member in archive.infolist():
        entry = Path(member.filename)
        label = prefix + member.filename
        if any(part.startswith(("pytest", "test_")) for part in entry.parts):
            continue
        if entry.suffix.lower() == ".zip":
            if depth >= 4:
                findings.append({"archive": archive_name, "member": label, "code": "ARCHIVE_DEPTH_LIMIT"})
                continue
            try:
                with zipfile.ZipFile(io.BytesIO(archive.read(member))) as nested:
                    yield from case_members(nested, archive_name=archive_name, findings=findings,
                                            prefix=label + "!", depth=depth + 1)
            except (OSError, ValueError, zipfile.BadZipFile, RuntimeError) as exc:
                findings.append({"archive": archive_name, "member": label,
                                 "code": "NESTED_ARCHIVE_UNREADABLE", "reason": str(exc)})
        elif entry.suffix.lower() in {".json", ".jsonl"}:
            content = archive.read(member)
            if entry.stem.lower().startswith(("case", "pair", "rejected")) or CASE_SCHEMA_VERSION.encode() in content:
                yield label, content


def archive_cases(root, output):
    """Read case members without extracting arbitrary paths or credentials from archives."""
    rows, archives, findings = [], {}, []
    for folder in ("archive", "artifacts", "exports", "release"):
        for path in sorted((root / folder).rglob("*.zip")):
            if path.is_relative_to(output) or any(part.startswith(("pytest", "test_")) for part in path.relative_to(root).parts):
                continue
            name = path.relative_to(root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            report = {"sha256": digest, "members": [], "case_occurrences": 0}
            archives[name] = report
            try:
                with zipfile.ZipFile(path) as archive:
                    for label, content in case_members(archive, archive_name=name, findings=findings):
                        entry = Path(label)
                        item = {"member": label, "sha256": hashlib.sha256(content).hexdigest(), "cases": 0}
                        report["members"].append(item)
                        try:
                            text = content.decode("utf-8-sig")
                            documents = [json.loads(line) for line in text.splitlines() if line.strip()] if entry.suffix.lower() == ".jsonl" else [json.loads(text)]
                            for document in documents:
                                for pointer, raw in _cases(document):
                                    case = case_from_dict(raw, allow_dynamic=True)
                                    rows.append(case.as_dict())
                                    item["cases"] += 1
                                    item.setdefault("bindings", []).append({"pointer": pointer, "case_sha256": case.content_sha256()})
                                    report["case_occurrences"] += 1
                        except (UnicodeError, ValueError, TypeError, KeyError) as exc:
                            findings.append({"archive": name, "member": label, "code": "ARCHIVE_MEMBER_NOT_INDEXABLE", "reason": str(exc)})
            except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                findings.append({"archive": name, "code": "ARCHIVE_UNREADABLE", "reason": str(exc)})
    source = output / "source/archived-cases.jsonl"
    source.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    if source.exists() and source.read_text(encoding="utf-8") != content:
        raise ValueError("archived case inventory changed; use a new output directory")
    if not source.exists():
        source.write_text(content, encoding="utf-8", newline="\n")
    return source, {"archives": archives, "findings": findings, "case_occurrences": len(rows),
                    "scope": "Retained ZIP case/pair/rejected and all case-schema-marked JSON members, including nested ZIPs to depth four; unreadable/deeper members explicit; test fixtures excluded."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archives", action="store_true", help="include retained ZIP case members with explicit archive provenance")
    args = parser.parse_args()
    archive_report = None
    if args.archives:
        source, archive_report = archive_cases(ROOT, args.output.resolve())
        index = build_index(ROOT, sources=[*discover_sources(ROOT), source])
        index["source_sha256"].update({name: row["sha256"] for name, row in archive_report["archives"].items()})
        index["summary"]["sources"] = len(index["source_sha256"])
        index["archive_inventory_sha256"] = canonical_sha256(archive_report)
        index["scope"]["archives"] = archive_report["scope"]
        archive_path = args.output / "ARCHIVE_INVENTORY.json"
        if archive_path.exists() and json.loads(archive_path.read_text(encoding="utf-8")) != archive_report:
            raise ValueError("immutable archive inventory changed; use a new output directory")
        if not archive_path.exists():
            atomic_json(archive_path, archive_report)
    else:
        index = build_index(ROOT)
    verify_sources(ROOT, index)
    summary = {key: value for key, value in index.items() if key != "records"}
    summary.update(index_sha256=canonical_sha256(index), provider_calls=0,
                   engineering_status="INDEXED_WITH_EXPLICIT_LIMITATIONS",
                   behavioral_history_status="NOT_RUN", scientific_acceptance=False)
    for name, value in (("INDEX.json", index), ("SUMMARY.json", summary)):
        target = args.output / name
        if target.exists():
            if json.loads(target.read_text(encoding="utf-8")) != value:
                raise ValueError(f"immutable historical index changed: {target}; use a new output directory")
        else:
            atomic_json(target, value)
    print(json.dumps({"output": str(args.output.resolve()), "summary": index["summary"],
                      "findings": len(index["findings"]), "index_sha256": summary["index_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
