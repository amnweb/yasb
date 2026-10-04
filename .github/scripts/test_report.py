"""Turn pytest results into the PR comment and job summary.

    test_report.py summarize --junit junit.xml --log pytest.log --exit-code FILE --label x64 --out report.json
    test_report.py comment --reports DIR --out comment.md --status status.txt

`summarize` runs next to pytest. `comment` runs in the PR Comment workflow from the default branch,
so it reads the reports as data and never executes anything from the pull request.
"""

import argparse
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

MARKER = "<!-- yasb-bot:tests -->"
MAX_FAILURES = 25
MAX_MESSAGE = 2500
LOG_TAIL_LINES = 60
CRASH_MARKERS = ("Fatal Python error", "Windows fatal exception")


def _node_id(classname: str, name: str) -> str:
    parts = classname.split(".")
    for split in range(len(parts), 0, -1):
        path = Path(*parts[:split]).with_suffix(".py")
        if path.is_file():
            return "::".join([path.as_posix(), *parts[split:], name])
    return f"{classname}::{name}"


def _failure_text(element: ET.Element) -> str:
    message = element.get("message") or ""
    text = (element.text or "").strip()
    return message if len(message) > 40 else text or message


def _exit_code(path: Path | None) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8-sig").strip())
    except (AttributeError, OSError, ValueError):
        return None


def summarize(junit: Path, log: Path, label: str, exit_code: int | None = None) -> dict:
    report = {"label": label, "counts": {}, "failures": [], "log_tail": "", "exit_code": exit_code}
    if not junit.is_file():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.is_file() else []
        # faulthandler's dump starts with the crashing test's frame; the end of the log is pytest internals.
        starts = [i for i, line in enumerate(lines) if line.startswith(CRASH_MARKERS)]
        excerpt = lines[starts[-1] : starts[-1] + LOG_TAIL_LINES] if starts else lines[-LOG_TAIL_LINES:]
        report["status"] = "crashed"
        report["log_tail"] = "\n".join(excerpt)
        return report

    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "xfailed": 0}
    for case in ET.parse(junit).iter("testcase"):
        node_id = _node_id(case.get("classname", ""), case.get("name", ""))
        problem = case.find("failure")
        error = case.find("error")
        skipped = case.find("skipped")
        if problem is not None:
            counts["failed"] += 1
            report["failures"].append({"id": node_id, "message": _failure_text(problem)})
        elif error is not None:
            counts["errors"] += 1
            report["failures"].append({"id": node_id, "message": _failure_text(error)})
        elif skipped is not None:
            counts["xfailed" if skipped.get("type") == "pytest.xfail" else "skipped"] += 1
        else:
            counts["passed"] += 1
    report["counts"] = counts
    if exit_code not in (None, 0, 1) and not report["failures"]:
        report["failures"].append({"id": "pytest", "message": f"pytest exited with code {exit_code}, see the job log"})
    report["status"] = "failure" if report["failures"] else "success"
    return report


def _table(reports: list[dict]) -> list[str]:
    lines = ["| | Passed | Failed | Errors | Skipped | Known issues |", "|---|---:|---:|---:|---:|---:|"]
    for report in reports:
        if report["status"] == "crashed":
            lines.append(f"| {report['label']} | pytest crashed before writing results | | | | |")
            continue
        c = report["counts"]
        lines.append(
            f"| {report['label']} | {c['passed']} | {c['failed']} | {c['errors']} | {c['skipped']} | {c['xfailed']} |"
        )
    return lines


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n... (truncated, see the job log)"


def render(reports: list[dict], *, with_marker: bool) -> str:
    failed = any(report["status"] != "success" for report in reports)
    lines = [MARKER] if with_marker else []
    lines.append("## ❌ Tests Failed" if failed else "## ✅ Tests Passed")
    lines += ["", *_table(reports), ""]

    for report in reports:
        if report["status"] == "crashed":
            code = report.get("exit_code")
            code_text = f" (exit code {code & 0xFFFFFFFF:#010x})" if isinstance(code, int) else ""
            lines += [
                f"### 💥 pytest crashed on {report['label']}{code_text}",
                "",
                "The process died before it could report. That is what an access violation in native code "
                "looks like, usually a ctypes signature or structure that does not match Windows. From the log:",
                "",
                "```text",
                report["log_tail"],
                "```",
                "",
            ]

    by_test: dict[str, dict] = {}
    for report in reports:
        for failure in report["failures"]:
            entry = by_test.setdefault(failure["id"], {"message": failure["message"], "labels": []})
            entry["labels"].append(report["label"])

    if by_test:
        lines += ["### Failures", ""]
        for node_id, entry in list(by_test.items())[:MAX_FAILURES]:
            lines += [
                f"<details><summary><code>{node_id}</code> ({', '.join(entry['labels'])})</summary>",
                "",
                "```text",
                _clip(entry["message"], MAX_MESSAGE),
                "```",
                "",
                f'Run it locally: `python -m pytest "{node_id}"`',
                "</details>",
                "",
            ]
        if len(by_test) > MAX_FAILURES:
            lines += [f"...and {len(by_test) - MAX_FAILURES} more, see the job summary.", ""]

    if failed:
        repository = os.environ.get("GITHUB_REPOSITORY")
        readme = "tests/README.md"
        if repository:
            server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
            readme = f"[{readme}]({server}/{repository}/blob/HEAD/tests/README.md)"
        lines += [
            "---",
            f"**Note:** The build will be skipped until the tests pass. See {readme} for what each check guards against.",
        ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    one = commands.add_parser("summarize")
    one.add_argument("--junit", type=Path, required=True)
    one.add_argument("--log", type=Path, required=True)
    one.add_argument("--exit-code", type=Path)
    one.add_argument("--label", required=True)
    one.add_argument("--out", type=Path, required=True)
    one.add_argument("--summary", type=Path)

    many = commands.add_parser("comment")
    many.add_argument("--reports", type=Path, required=True)
    many.add_argument("--out", type=Path, required=True)
    many.add_argument("--status", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "summarize":
        report = summarize(args.junit, args.log, args.label, _exit_code(args.exit_code))
        args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        if args.summary:
            with args.summary.open("a", encoding="utf-8") as summary:
                summary.write(render([report], with_marker=False))
        return 0

    paths = sorted(args.reports.glob("report-*.json")) if args.reports.is_dir() else []
    reports = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    if not reports:
        args.status.write_text("unknown", encoding="utf-8")
        return 0
    failed = any(report["status"] != "success" for report in reports)
    args.status.write_text("failure" if failed else "success", encoding="utf-8")
    args.out.write_text(render(reports, with_marker=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
