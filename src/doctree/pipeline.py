"""Load inputs, save inspectable results, then optionally score a separate truth file."""

import hashlib
import platform
from collections import Counter
from dataclasses import fields
from time import perf_counter

from doctree.config import Config
from doctree.fixes import CHANGE_FIELDS
from doctree.io import (
    DOC_FIELDS,
    REQUIRED_FIELDS,
    TREE_FIELDS,
    TRUTH_FIELDS,
    read_csv,
    write_csv,
    write_json,
)
from doctree.models import Issue
from doctree.scoring import score
from doctree.validation import validate

COMPLETENESS_FIELDS = TREE_FIELDS + [
    "equipment_class",
    "required_count",
    "present_count",
    "missing_count",
    "completeness_pct",
    "missing_types",
]
ISSUE_FIELDS = [field.name for field in fields(Issue)]


def check(config: Config) -> dict:
    start = perf_counter()
    tree_path = config.data_dir / "equipment_tree.csv"
    docs_path = config.data_dir / "document_register.csv"
    rules_path = config.data_dir / "required_docs.csv"
    tree = read_csv(tree_path, TREE_FIELDS)
    documents = read_csv(docs_path, [f for f in DOC_FIELDS if f != "row_id"])
    generated_ids = bool(documents) and "row_id" not in documents[0]
    if generated_ids:
        for index, row in enumerate(documents, start=1):
            row["row_id"] = f"ROW-{index:06d}"
    required = read_csv(rules_path, REQUIRED_FIELDS)
    result = validate(tree, documents, required, config)
    # The detector has finished before the optional answer key is ever read.
    truth_path = config.data_dir / "injected_errors.csv"
    scoring = None
    if truth_path.exists():
        scoring = score(result.issues, result.changes, read_csv(truth_path, TRUTH_FIELDS))
    issue_rows = [i.as_dict() for i in result.issues]
    manual = [
        dict(review_id=f"REV-{index:06d}", **row, decision="Pending", initials="", reviewed_at="")
        for index, row in enumerate(issue_rows, start=1)
    ]
    output = config.reports_dir
    write_csv(output / "issues.csv", ISSUE_FIELDS, issue_rows)
    write_csv(
        output / "manual_review.csv",
        ["review_id", *ISSUE_FIELDS, "decision", "initials", "reviewed_at"],
        manual,
    )
    write_csv(output / "change_log.csv", CHANGE_FIELDS, result.changes)
    write_csv(output / "document_register_cleaned.csv", DOC_FIELDS, result.documents)
    write_csv(output / "completeness.csv", COMPLETENESS_FIELDS, result.completeness)
    equipment = [r for r in result.completeness if r["level"] == "Equipment"]
    needed = sum(r["required_count"] for r in equipment)
    present = sum(r["present_count"] for r in equipment)
    paths = [tree_path, docs_path, rules_path]
    if scoring is not None:
        paths.append(truth_path)
    summary = dict(
        synthetic=True,
        seed=config.seed,
        as_of_date=config.as_of_date.isoformat(),
        python_version=platform.python_version(),
        document_count=len(documents),
        equipment_count=len(equipment),
        node_count=len(tree),
        system_count=sum(r["level"] == "System" for r in tree),
        subsystem_count=sum(r["level"] == "Subsystem" for r in tree),
        issue_count=len(result.issues),
        issues_per_rule=dict(sorted(Counter(i.rule for i in result.issues).items())),
        issues_per_severity=dict(sorted(Counter(i.severity for i in result.issues).items())),
        change_count=len(result.changes),
        manual_review_count=len(manual),
        completeness=dict(
            required_count=needed,
            present_count=present,
            missing_count=needed - present,
            completeness_pct=round(100 * present / needed, 4) if needed else None,
            trustworthy_tree=result.tree_trustworthy,
            basis="Required type coverage by mapped issued metadata records only",
        ),
        row_ids_from_source=not generated_ids,
        title_similarity_threshold=config.title_similarity_threshold,
        filename_template=config.filename_template,
        input_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        scoring_available=scoring is not None,
    )
    if scoring is not None:
        write_json(output / "scoring.json", scoring)
    else:
        (output / "scoring.json").unlink(missing_ok=True)
    summary["runtime_seconds"] = round(perf_counter() - start, 6)
    summary["runtime_scope"] = (
        "Input load, detection, CSV export and scoring; excludes summary write"
    )
    write_json(output / "summary.json", summary)
    return summary
