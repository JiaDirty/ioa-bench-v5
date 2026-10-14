"""One-off surgical repair: make PROJECT_STATE.yaml parseable by quoting only the plain scalars
that actually break yaml.safe_load (pre-existing prose values containing ': ' sequences).

Loop: parse -> on ScannerError at line N, single-quote that line's value (after 'key: ' or '- key: ')
-> re-parse. Never touches quoted, block (|/>), flow ([/{), anchor (&) or empty values. Content is
preserved verbatim; only the quoting changes. Backs up the original beside the file first.
"""
import re
import shutil
import sys
from pathlib import Path

import yaml

PATH = Path("state/PROJECT_STATE.yaml")
KEY_RE = re.compile(r"^(?P<indent>\s*(?:- )?(?:[A-Za-z_][\w.]*|\")(?P<sep>\s*:\s*))(?P<value>.+)$")


def quote_value(line: str) -> str | None:
    m = KEY_RE.match(line)
    if not m:
        return None
    value = m.group("value")
    if value.startswith(("'", '"', "|", ">", "[", "{", "&", "*", "#")) or value == "":
        return None
    if ": " not in value and not value.endswith(":"):
        return None
    quoted = "'" + value.replace("'", "''") + "'"
    return m.group("indent") + quoted


def main() -> int:
    apply = "--apply" in sys.argv
    original = PATH.read_text(encoding="utf-8")
    shutil.copy2(PATH, PATH.with_suffix(".yaml.bak-preyamlfix"))
    lines = original.splitlines()
    fixed: list[tuple[int, str, str]] = []
    for _ in range(60):
        try:
            yaml.safe_load("\n".join(lines) + "\n")
            break
        except yaml.scanner.ScannerError as exc:
            mark = exc.problem_mark
            if mark is None:
                print(f"UNFIXABLE error without mark: {exc}")
                return 1
            idx = mark.line  # 0-based
            line = lines[idx]
            repaired = quote_value(line)
            if repaired is None:
                print(f"UNFIXABLE line {idx + 1}: {line[:100]!r}")
                return 1
            fixed.append((idx + 1, line[:80], repaired[:80]))
            lines[idx] = repaired
        except yaml.parser.ParserError as exc:
            mark = exc.problem_mark
            print(f"PARSER error at line {mark.line + 1 if mark else '?'}: {str(exc)[:200]}")
            return 1
    else:
        print("did not converge in 60 iterations")
        return 1
    if not fixed:
        print("nothing to fix (already parseable)")
        return 0
    for lineno, before, after in fixed:
        print(f"line {lineno}: quoted ({before[:60]!r} -> {after[:60]!r})")
    if apply:
        PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        data = yaml.safe_load(PATH.read_text(encoding="utf-8"))
        print(f"APPLIED {len(fixed)} fixes; parse OK; top-level keys: {len(data)}")
    else:
        print("DRY RUN (pass --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
