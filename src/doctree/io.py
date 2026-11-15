"""Small, explicit CSV and JSON boundaries."""

import csv
import json
from pathlib import Path

TREE_FIELDS = ["code", "parent_code", "level", "name"]
DOC_FIELDS = [
    "row_id",
    "doc_id",
    "title",
    "doc_type",
    "equipment_code",
    "revision",
    "status",
    "issue_date",
    "file_name",
    "page_count",
]
REQUIRED_FIELDS = ["equipment_class", "doc_type"]
TRUTH_FIELDS = [
    "injection_id",
    "error_type",
    "rule",
    "entity_type",
    "entity_id",
    "field",
    "before",
    "after",
    "description",
]


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path, required: list[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"{path.name}: missing or duplicate column headers")
        missing = set(required) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path.name}: missing columns: {', '.join(sorted(missing))}")
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) for row in rows):
            raise ValueError(f"{path.name}: malformed CSV row")
        return rows


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
