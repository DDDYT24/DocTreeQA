"""Render the README's numeric claims directly from saved reports, never estimates."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def percent(value):
    return f"{100 * value:.2f}%" if value is not None else "N/A"


def main():
    summary = json.loads((REPORTS / "summary.json").read_text())
    scoring = json.loads((REPORTS / "scoring.json").read_text())
    suites = list(ET.parse(REPORTS / "pytest-results.xml").getroot().iter("testsuite"))
    tests = sum(int(suite.attrib["tests"]) for suite in suites)
    failures = sum(int(suite.attrib["failures"]) for suite in suites)
    errors = sum(int(suite.attrib["errors"]) for suite in suites)
    skipped = sum(int(suite.attrib["skipped"]) for suite in suites)
    if failures or errors:
        raise ValueError("Refuse to present a failing test run as a successful result")
    workbook = json.loads((REPORTS / "workbook_manifest.json").read_text())
    if (
        hashlib.sha256((REPORTS / workbook["workbook"]).read_bytes()).hexdigest()
        != workbook["workbook_sha256"]
    ):
        raise ValueError("Workbook no longer matches its saved manifest")
    for name, digest in workbook["source_sha256"].items():
        if hashlib.sha256((REPORTS / name).read_bytes()).hexdigest() != digest:
            raise ValueError(
                f"Workbook source changed; rerun report before updating README: {name}"
            )
    vba = json.loads((REPORTS / "vba_syntax_check.json").read_text())
    if (
        hashlib.sha256((ROOT / "vba/DocTreeQA.bas").read_bytes()).hexdigest()
        != vba["module_sha256"]
    ):
        raise ValueError("VBA source changed; rerun its syntax validation")
    publication_path = REPORTS / "publication.json"
    publication = json.loads(publication_path.read_text()) if publication_path.exists() else {}
    ci_path = REPORTS / "ci_status.json"
    ci = json.loads(ci_path.read_text()) if ci_path.exists() else {}
    acceptance_path = REPORTS / "windows_excel_acceptance.json"
    acceptance = json.loads(acceptance_path.read_text()) if acceptance_path.exists() else {}
    runtime_confirmed = (
        acceptance.get("main_workflow_passed") is True
        and acceptance.get("module_source_sha256") == vba["module_sha256"]
    )
    published = publication.get("status") == "published"
    ci_passed = ci.get("conclusion") == "success"
    milestones = ["M0", "M1", "M2"]
    if runtime_confirmed:
        milestones.append("M3")
    if published and ci_passed:
        milestones.append("M4")
    incomplete = []
    if not runtime_confirmed:
        incomplete.append("Windows Excel verification")
    if not acceptance.get("screenshot_files_archived"):
        incomplete.append("Archive approved Windows Excel screenshot files")
    if not published:
        incomplete.append("Public GitHub publication")
    if not ci_passed:
        incomplete.append("Hosted GitHub Actions verification")
    verification = dict(
        milestones=milestones,
        m3_status=(
            "Main workflow passed in a user-run Windows Excel session; "
            "evidence files pending archiving"
            if runtime_confirmed
            else "Module implemented; static syntax passed; Windows Excel acceptance pending"
        ),
        m4_status=(
            "Published with hosted CI verified"
            if published and ci_passed
            else "Documentation and local handoff prepared; publication and hosted CI pending"
        ),
        python_version=summary["python_version"],
        pytest=dict(
            tests=tests,
            passed=tests - skipped,
            failures=failures,
            errors=errors,
            skipped=skipped,
            source="reports/pytest-results.xml",
        ),
        local_checks=["ruff check .", "ruff format --check .", "pytest"],
        remote_ci_status=ci,
        publication=publication,
        workbook=workbook,
        vba_syntax_status=vba["status"],
        vba_runtime_status=(
            "Main workflow passed by user report and supplied screenshots"
            if runtime_confirmed
            else "Not run; Windows Excel acceptance pending"
        ),
        windows_excel_acceptance=acceptance,
        incomplete=incomplete,
    )
    (REPORTS / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
    rows = [
        ("Python runtime", summary["python_version"]),
        ("Systems", summary["system_count"]),
        ("Subsystems", summary["subsystem_count"]),
        ("Equipment items", summary["equipment_count"]),
        ("Document register rows", summary["document_count"]),
        ("Findings requiring review", summary["issue_count"]),
        ("Logged safe changes", summary["change_count"]),
        (
            "Required type coverage",
            f"{summary['completeness']['present_count']} / "
            f"{summary['completeness']['required_count']} "
            f"({summary['completeness']['completeness_pct']}%)",
        ),
        ("Scored expected findings, including safe changes", scoring["overall"]["support"]),
        ("Overall synthetic precision", percent(scoring["overall"]["precision"])),
        ("Overall synthetic recall", percent(scoring["overall"]["recall"])),
        ("False positives", scoring["overall"]["false_positives"]),
        ("False negatives", scoring["overall"]["false_negatives"]),
        ("Measured runtime, seconds", summary["runtime_seconds"]),
        ("Passing local pytest cases", verification["pytest"]["passed"]),
        ("Workbook sheets", len(workbook["data_rows"])),
    ]
    text = "| Measure | Saved value |\n| --- | --- |\n"
    text += "\n".join(f"| {name} | {value} |" for name, value in rows)
    text += "\n\nPer-rule results with injected examples:\n\n"
    text += "| Rule | Expected | Detected | Precision | Recall |\n| --- | --- | --- | --- | --- |\n"
    for rule, values in scoring["per_rule"].items():
        if not values["support"]:
            continue
        text += (
            f"| `{rule}` | {values['support']} | {values['true_positives']} | "
            f"{percent(values['precision'])} | {percent(values['recall'])} |\n"
        )
    text += (
        "\nOther rules have no injected examples in the default benchmark; their recall "
        "is N/A in the scoring JSON. Numeric results above come from the saved summary, "
        "scoring and test XML files. Rerun `python scripts/update_readme_results.py` "
        "after updating those outputs.\n"
    )
    path = ROOT / "README.md"
    content = path.read_text()
    updated, count = re.subn(
        r"<!-- RESULTS:START -->.*?<!-- RESULTS:END -->",
        "<!-- RESULTS:START -->\n" + text + "<!-- RESULTS:END -->",
        content,
        flags=re.DOTALL,
    )
    if count != 1:
        raise ValueError("Expected exactly one README results block")
    path.write_text(updated)
    if runtime_confirmed and "<!-- WINDOWS:START -->" in updated:
        environment = acceptance["environment"]
        observed = acceptance["observed_review"]
        windows_text = (
            "| Recorded Windows Excel result | Value |\n| --- | --- |\n"
            f"| Test date | {acceptance['test_date']} |\n"
            f"| Excel version | {environment['excel_version']} |\n"
            f"| Excel build | {environment['excel_build']} |\n"
            f"| Excel bitness | {environment['excel_bitness']} |\n"
            f"| Open findings after rejection | {observed['open_findings_after_rejection']} |\n"
            f"| Open findings after reopening | {observed['open_findings_after_reopening']} |\n"
            f"| Added review audit rows | {observed['review_log_rows_added']} |\n"
        )
        updated, count = re.subn(
            r"<!-- WINDOWS:START -->.*?<!-- WINDOWS:END -->",
            "<!-- WINDOWS:START -->\n" + windows_text + "<!-- WINDOWS:END -->",
            updated,
            flags=re.DOTALL,
        )
        if count != 1:
            raise ValueError("Expected exactly one Windows acceptance results block")
        path.write_text(updated)


if __name__ == "__main__":
    main()
