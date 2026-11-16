"""Save Python reference counts for a later, separately observed Windows Excel run."""

import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def prepare(root: Path = ROOT) -> dict:
    folder = root / "reports"

    def read(name):
        with (folder / name).open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    issues, manual, tree = read("issues.csv"), read("manual_review.csv"), read("completeness.csv")
    names = {r["code"]: r["name"] for r in tree if r["level"] == "System"}
    counts = {
        code: dict(
            system_code=code, system_name=name, error=0, warning=0, info=0, other=0, total_open=0
        )
        for code, name in names.items()
    }
    for issue in issues:
        if issue["review_status"] == "Dismissed":
            continue
        if issue["review_status"] != "Open":
            raise ValueError("Unexpected review status in reference data")
        code = issue["system_code"] if issue["system_code"] in names else "Unmapped / Unknown"
        if code not in counts:
            counts[code] = dict(
                system_code=code,
                system_name="No valid System assignment",
                error=0,
                warning=0,
                info=0,
                other=0,
                total_open=0,
            )
        severity = (
            issue["severity"] if issue["severity"] in {"error", "warning", "info"} else "other"
        )
        counts[code][severity] += 1
        counts[code]["total_open"] += 1
    fields = ["system_code", "system_name", "error", "warning", "info", "other", "total_open"]
    with (folder / "system_summary_expected.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(counts.values())
    total = sum(row["total_open"] for row in counts.values())
    first = manual[0] if manual else None
    reference = dict(
        synthetic=True,
        meaning="Python expectations for manual Windows Excel tests; not VBA execution evidence",
        workbook_sha256=hashlib.sha256((folder / "doctree_report.xlsx").read_bytes()).hexdigest(),
        initial_open_findings=total,
        initial_system_rows=len(counts),
        initial_unmapped_open=counts.get("Unmapped / Unknown", {}).get("total_open", 0),
        first_review_id=first["review_id"] if first else None,
        first_finding={
            key: first[key] for key in ("rule", "entity_type", "entity_id", "system_code")
        }
        if first
        else None,
        after_accepting_first_row=total if first else None,
        after_rejecting_same_first_row=total - 1 if first else None,
        expected_severity_colours={"error": "FCE4D6", "warning": "FFF2CC", "info": "E7E6E6"},
        vba_runtime_status=(
            "Not run by this reference generator; observed runtime evidence is separate"
        ),
    )
    (folder / "excel_acceptance_reference.json").write_text(json.dumps(reference, indent=2) + "\n")
    return reference


if __name__ == "__main__":
    print(json.dumps(prepare(), indent=2))
