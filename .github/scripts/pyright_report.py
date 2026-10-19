"""Turn Pyright's JSON output into the PR comment, the job log and the job summary.

    pyright_report.py summarize --json pyright.json --exit-code FILE --out report.json --summary FILE
    pyright_report.py comment --report report.json --out comment.md --status status.txt

`summarize` runs next to Pyright. `comment` runs in the PR Comment workflow from the default branch,
so it reads the report as data and never executes anything from the pull request.
"""

import argparse
import json
import re
from pathlib import Path
from typing import TypedDict

MARKER = "<!-- yasb-bot:pyright -->"
SEVERITIES = ("error", "warning")
MAX_DIAGNOSTICS = 100
MAX_MESSAGE = 1000


class Diagnostic(TypedDict):
    file: str
    line: int
    column: int
    severity: str
    message: str
    rule: str


class Report(TypedDict):
    status: str
    exit_code: int | None
    errors: int
    warnings: int
    diagnostics: list[Diagnostic]


def _exit_code(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        return int(path.read_text(encoding="utf-8-sig").strip())
    except (OSError, ValueError):
        return None


def _relative(file: str, root: Path) -> str:
    try:
        return Path(file).relative_to(root).as_posix()
    except ValueError:
        return Path(file).as_posix()


def summarize(output: Path, exit_code: int | None, root: Path) -> Report:
    report: Report = {"status": "crashed", "exit_code": exit_code, "errors": 0, "warnings": 0, "diagnostics": []}
    try:
        data = json.loads(output.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return report

    for item in data.get("generalDiagnostics", []):
        if item.get("severity") not in SEVERITIES:
            continue
        start = item.get("range", {}).get("start", {})
        diagnostic: Diagnostic = {
            "file": _relative(item.get("file", ""), root),
            "line": start.get("line", 0) + 1,
            "column": start.get("character", 0) + 1,
            "severity": item["severity"],
            "message": item.get("message", ""),
            "rule": item.get("rule", ""),
        }
        report["diagnostics"].append(diagnostic)
    report["diagnostics"].sort(key=lambda item: (item["file"], item["line"], item["column"]))
    summary = data.get("summary", {})
    report["errors"] = summary.get("errorCount", 0)
    report["warnings"] = summary.get("warningCount", 0)
    failed = report["errors"] > 0 or exit_code not in (None, 0)
    report["status"] = "failure" if failed else "success"
    return report


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _fence(text: str) -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " ... (truncated, see the job log)"


def _listing(diagnostics: list[Diagnostic]) -> str:
    lines: list[str] = []
    current: str | None = None
    for item in diagnostics:
        if item["file"] != current:
            current = item["file"]
            lines.append(("\n" if lines else "") + current)
        rule = f" ({item['rule']})" if item["rule"] else ""
        message = _clip(item["message"], MAX_MESSAGE).replace("\n", "\n    ")
        lines.append(f"  {item['line']}:{item['column']} - {item['severity']}: {message}{rule}")
    return "\n".join(lines)


def render(report: Report, *, with_marker: bool) -> str:
    failed = report["status"] != "success"
    lines = [MARKER] if with_marker else []
    lines.append("## ❌ Pyright Type Check Failed" if failed else "## ✅ Pyright Type Check Passed")
    lines.append("")

    diagnostics = report["diagnostics"]
    if report["status"] == "crashed" or (failed and not diagnostics):
        lines += [
            f"Pyright exited with code {report['exit_code']} before reporting any diagnostics, see the job log.",
            "",
        ]
    elif diagnostics:
        files = len({item["file"] for item in diagnostics})
        found = _plural(report["errors"], "error")
        if report["warnings"]:
            found += f" and {_plural(report['warnings'], 'warning')}"
        lines += [
            f"Pyright found {found} in {_plural(files, 'file')}. It runs in strict mode with the settings from "
            "`[tool.pyright]` in `pyproject.toml`.",
            "",
        ]
        listing = _listing(diagnostics[:MAX_DIAGNOSTICS])
        fence = _fence(listing)
        lines += [f"{fence}text", listing, fence, ""]
        if len(diagnostics) > MAX_DIAGNOSTICS:
            lines += [f"...and {len(diagnostics) - MAX_DIAGNOSTICS} more, see the job summary.", ""]

    if failed:
        lines += [
            "**To fix:** Install the pinned Pyright with `pip install -e .[dev]`, run `pyright` and fix what it "
            "reports. Pylance in VS Code reads the same settings, so most of these errors also show up in the editor.",
            "",
            "---",
            "**Note:** The build will be skipped until these issues are resolved.",
        ]
    return "\n".join(lines) + "\n"


def _escape(value: str, *, in_property: bool = False) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return value.replace(":", "%3A").replace(",", "%2C") if in_property else value


def _print_log(report: Report) -> None:
    diagnostics = report["diagnostics"]
    if diagnostics:
        print(_listing(diagnostics))
    print(f"{_plural(report['errors'], 'error')}, {_plural(report['warnings'], 'warning')}")
    for item in diagnostics:
        title = f"Pyright ({item['rule']})" if item["rule"] else "Pyright"
        properties = f"file={_escape(item['file'], in_property=True)},line={item['line']},col={item['column']}"
        print(f"::{item['severity']} {properties},title={_escape(title, in_property=True)}::{_escape(item['message'])}")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    one = commands.add_parser("summarize")
    one.add_argument("--json", type=Path, required=True)
    one.add_argument("--exit-code", type=Path)
    one.add_argument("--root", type=Path, default=Path.cwd())
    one.add_argument("--out", type=Path, required=True)
    one.add_argument("--summary", type=Path)

    many = commands.add_parser("comment")
    many.add_argument("--report", type=Path, required=True)
    many.add_argument("--out", type=Path, required=True)
    many.add_argument("--status", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "summarize":
        report = summarize(args.json, _exit_code(args.exit_code), args.root.resolve())
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        _print_log(report)
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as summary:
                summary.write(render(report, with_marker=False))
        return 0

    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        body = render(report, with_marker=True)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        args.status.write_text("unknown", encoding="utf-8")
        return 0
    args.status.write_text("success" if report.get("status") == "success" else "failure", encoding="utf-8")
    args.out.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
