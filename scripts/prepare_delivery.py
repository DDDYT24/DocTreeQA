"""Collect saved evidence and write private draft bullets beside the project."""

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def main():
    summary = json.loads((REPORTS / "summary.json").read_text())
    scoring = json.loads((REPORTS / "scoring.json").read_text())
    verification = json.loads((REPORTS / "verification.json").read_text())
    receipt = dict(
        synthetic=True,
        summary=summary,
        scoring=scoring,
        pytest=verification["pytest"],
        publication=verification["publication"],
        hosted_ci=verification["remote_ci_status"],
        incomplete=verification["incomplete"] + ["Optional public P&ID transcription exercise"],
        sources=["reports/summary.json", "reports/scoring.json", "reports/verification.json"],
    )
    (REPORTS / "delivery_metrics.json").write_text(json.dumps(receipt, indent=2) + "\n")
    precision = scoring["overall"]["precision"]
    recall = scoring["overall"]["recall"]
    if precision is None or recall is None:
        raise ValueError("Resume metric wording requires scored examples")
    performance = (
        f"{precision:.0%} precision and recall"
        if precision == recall
        else f"{precision:.0%} precision and {recall:.0%} recall"
    )
    bullets = [
        f"Built Python automation to map {summary['document_count']:,} synthetic document records "
        f"to a hierarchical structure of {summary['equipment_count']:,} equipment items.",
        f"Flagged {summary['issue_count']:,} metadata and completeness issues for manual review "
        f"and logged {summary['change_count']:,} safe data cleaning changes.",
        f"Verified data validation with {verification['pytest']['passed']:,} passing tests "
        f"and {performance} on controlled synthetic faults.",
        "Created an Excel workbook and a VBA module for issue highlighting, System summaries "
        "and review logging.",
    ]
    lines = []
    for bullet in bullets:
        if any(character in bullet for character in "-–—"):
            raise ValueError("Bullet drafts must not contain hyphens or dashes")
        wrapped = textwrap.wrap(bullet, width=78, break_long_words=False)
        if len(wrapped) > 2:
            raise ValueError("A bullet draft exceeds two lines at the selected text width")
        lines.append("\n".join(wrapped))
    note = "DocTreeQA resume bullet drafts\n\nDraft wording based on saved project outputs. " + (
        "The main VBA workflow was verified in a user-run Windows Excel session.\n\n"
        if "M3" in verification["milestones"]
        else "Windows Excel compilation and execution remain pending.\n\n"
    )
    target = ROOT.parent / "DocTreeQA-resume-bullets.txt"
    target.write_text(
        note + "\n\n".join(lines) + "\n\n"
        "Evidence: reports/summary.json, reports/scoring.json, "
        "reports/verification.json and vba/DocTreeQA.bas.\n"
    )
    print(target)


if __name__ == "__main__":
    main()
