"""Generate fictional records and record expected findings without running detectors."""

import json
import random
from datetime import timedelta

from doctree.config import Config
from doctree.io import DOC_FIELDS, REQUIRED_FIELDS, TREE_FIELDS, TRUTH_FIELDS, write_csv, write_json


def generate(config: Config, *, force: bool = False) -> dict:
    output_names = [
        "equipment_tree.csv",
        "document_register.csv",
        "required_docs.csv",
        "injected_errors.csv",
        "manifest.json",
        "README.md",
    ]
    if not force and any((config.data_dir / name).exists() for name in output_names):
        raise ValueError("Generated inputs already exist; use generate --force to replace them")
    rng = random.Random(config.seed)
    nodes = []
    for i in range(config.systems):
        nodes.append(
            {
                "code": f"{200 + i * 10}",
                "parent_code": "",
                "level": "System",
                "name": f"Fictional System {i + 1:03d}",
            }
        )
    systems = nodes.copy()
    subsystems = []
    for i in range(config.subsystems):
        system = systems[i % len(systems)]
        node = {
            "code": f"{system['code']}-{i // len(systems) + 1:02d}",
            "parent_code": system["code"],
            "level": "Subsystem",
            "name": f"Fictional Assembly {i + 1:03d}",
        }
        subsystems.append(node)
    nodes.extend(subsystems)
    equipment = []
    classes = tuple(config.required_by_class)
    for i in range(config.equipment):
        subsystem = subsystems[i % len(subsystems)]
        code = f"{subsystem['code']}-{i // len(subsystems) + 1:02d}"
        equipment.append(
            {
                "code": code,
                "parent_code": subsystem["code"],
                "level": "Equipment",
                "name": f"{classes[i % len(classes)].title()} Unit {code}",
            }
        )
    nodes.extend(equipment)
    docs = []

    def append_doc(record: dict) -> dict:
        row = dict(record, row_id=f"ROW-{len(docs) + 1:06d}")
        docs.append(row)
        return row

    # One current document per type and equipment forms a known-complete baseline.
    for item in equipment:
        for doc_type in config.doc_types:
            doc_id = f"SYN-{len(docs) + 1:06d}"
            append_doc(
                {
                    "doc_id": doc_id,
                    "title": f"{item['name']} {doc_type.replace('_', ' ')}",
                    "doc_type": doc_type,
                    "equipment_code": item["code"],
                    "revision": "2",
                    "status": "issued",
                    "issue_date": (
                        config.as_of_date - timedelta(days=rng.randint(1, 700))
                    ).isoformat(),
                    "file_name": config.filename_template.format(doc_id=doc_id, revision="2"),
                    "page_count": str(rng.randint(1, 160)),
                }
            )
    current = docs.copy()
    remaining = config.documents - len(docs)
    for i in range(remaining):
        source = current[i % len(current)]
        # Distinct older revisions keep the baseline valid even with a larger register.
        old = dict(source)
        if i < len(current):
            old.update(revision="1", status="superseded")
        else:
            old.update(
                doc_id=f"SYN-EXTRA-{i + 1:06d}",
                revision="1",
                status="draft",
                title=f"{source['title']} appendix {i + 1}",
            )
        old["file_name"] = config.filename_template.format(**old)
        append_doc(old)

    truth = []
    event_number = 0

    def log(
        error_type: str,
        expectations: list[tuple[str, str, str]],
        field: str,
        before: str,
        after: str,
        description: str,
    ) -> None:
        nonlocal event_number
        event_number += 1
        for rule, entity_type, entity_id in expectations:
            truth.append(
                dict(
                    injection_id=f"INJ-{event_number:05d}",
                    error_type=error_type,
                    rule=rule,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    field=field,
                    before=before,
                    after=after,
                    description=description,
                )
            )

    error_types = [
        "missing_revision",
        "missing_title",
        "unknown_equipment",
        "filename_mismatch",
        "orphan_superseded",
        "future_date",
        "wrong_mapping_level",
        "safe_normalization",
        "invalid_doc_type",
        "invalid_status",
        "invalid_date",
        "invalid_page_count",
        "invalid_revision",
        "unmapped_document",
        "multiple_issued",
        "duplicate_doc_id",
        "duplicate_file",
        "near_duplicate_title",
        "missing_required",
    ]
    # Drawing is deliberately outside the required set, isolating mapping and metadata faults.
    if config.errors_per_type and any(
        "drawing" in values for values in config.required_by_class.values()
    ):
        raise ValueError("Synthetic fault isolation requires drawing to be a nonrequired type")
    candidates = [row for row in current if row["doc_type"] == "drawing"]
    needed = len(error_types) * config.errors_per_type
    if len(candidates) < needed:
        raise ValueError(f"Need at least {needed} equipment items for isolated error injections")
    rng.shuffle(candidates)
    serial = len(docs)
    removed_ids = set()
    for error_type in error_types:
        for _ in range(config.errors_per_type):
            row = candidates.pop()
            row_id = row["row_id"]
            field = ""
            before, after = "", ""
            rules = []
            if error_type == "missing_required":
                item = next(e for e in equipment if e["code"] == row["equipment_code"])
                required_type = config.required_by_class[item["name"].split()[0].lower()][0]
                removed = [
                    d
                    for d in docs
                    if d["equipment_code"] == item["code"] and d["doc_type"] == required_type
                ]
                removed_ids.update(d["row_id"] for d in removed)
                log(
                    error_type,
                    [("missing_required", "requirement", f"{item['code']}|{required_type}")],
                    "document_rows",
                    json.dumps(removed, sort_keys=True),
                    "[]",
                    "Remove all revisions of one required document type",
                )
                continue
            if error_type in {"duplicate_doc_id", "duplicate_file", "near_duplicate_title"}:
                serial += 1
                clone = dict(row, row_id=f"ROW-{serial:06d}")
                if error_type == "duplicate_doc_id":
                    rules = ["duplicate_doc_id", "exact_duplicate"]
                else:
                    clone["doc_id"] = f"SYN-COPY-{serial:06d}"
                    if error_type == "duplicate_file":
                        rules = ["duplicate_file", "filename_mismatch", "near_duplicate_title"]
                    else:
                        clone["title"] = row["title"].upper().replace(" ", " / ")
                        clone["file_name"] = config.filename_template.format(**clone)
                        rules = ["near_duplicate_title"]
                docs.append(clone)
                log(
                    error_type,
                    [(rule, "row", clone["row_id"]) for rule in rules],
                    "document_rows",
                    json.dumps(row, sort_keys=True),
                    json.dumps(clone, sort_keys=True),
                    "Append a deliberately duplicated record",
                )
                continue
            if error_type == "orphan_superseded":
                related = [d for d in docs if d["doc_id"] == row["doc_id"]]
                before = row["status"]
                row["status"] = "superseded"
                log(
                    error_type,
                    [("superseded_without_replacement", "row", d["row_id"]) for d in related],
                    "status",
                    before,
                    row["status"],
                    "Remove the issued replacement from an existing revision lineage",
                )
                continue
            if error_type == "multiple_issued":
                old = next(
                    (d for d in docs if d["doc_id"] == row["doc_id"] and d["revision"] == "1"), None
                )
                if old is None:
                    raise ValueError(
                        "Revision fault injections require older revisions in documents"
                    )
                before = old["status"]
                old["status"] = "issued"
                log(
                    error_type,
                    [("multiple_issued", "document", row["doc_id"])],
                    "status",
                    before,
                    old["status"],
                    "Leave multiple issued revisions for a document",
                )
                continue
            if error_type == "safe_normalization":
                for field, after in [("title", f"  {row['title']}  "), ("doc_type", " DRAWING ")]:
                    before = row[field]
                    row[field] = after
                    log(
                        error_type,
                        [("safe_normalization", "change", f"{row_id}|{field}")],
                        field,
                        before,
                        after,
                        "Inject harmless whitespace or document type casing",
                    )
                continue
            mutations = {
                "missing_revision": ("revision", "", ["missing_revision"]),
                "missing_title": ("title", "", ["missing_title"]),
                "unknown_equipment": ("equipment_code", "UNKNOWN-SYNTHETIC", ["unknown_equipment"]),
                "filename_mismatch": (
                    "file_name",
                    f"SYN-wrong-{row_id}.pdf",
                    ["filename_mismatch"],
                ),
                "future_date": (
                    "issue_date",
                    (config.as_of_date + timedelta(days=30)).isoformat(),
                    ["future_date"],
                ),
                "wrong_mapping_level": (
                    "equipment_code",
                    rng.choice(subsystems + systems)["code"],
                    ["wrong_mapping_level"],
                ),
                "invalid_doc_type": ("doc_type", "spreadsheet", ["invalid_doc_type"]),
                "invalid_status": ("status", "approved", ["invalid_status"]),
                "invalid_date": ("issue_date", "2026-02-30", ["invalid_date"]),
                "invalid_page_count": ("page_count", "-5", ["invalid_page_count"]),
                "invalid_revision": ("revision", "two", ["invalid_revision"]),
                "unmapped_document": ("equipment_code", "", ["unmapped_document"]),
            }
            field, after, rules = mutations[error_type]
            before = row[field]
            row[field] = after
            # An invalid issued revision also removes a provably newer replacement.
            if error_type in {"missing_revision", "invalid_revision", "invalid_status"}:
                older = [
                    d for d in docs if d["doc_id"] == row["doc_id"] and d["status"] == "superseded"
                ]
                expectations = [(rule, "row", row_id) for rule in rules]
                expectations += [
                    ("superseded_without_replacement", "row", d["row_id"]) for d in older
                ]
            else:
                expectations = [(rule, "row", row_id) for rule in rules]
            log(
                error_type,
                expectations,
                field,
                before,
                after,
                "Deliberate synthetic metadata fault",
            )
    docs = [row for row in docs if row["row_id"] not in removed_ids]
    required = [
        dict(equipment_class=key, doc_type=value)
        for key, values in config.required_by_class.items()
        for value in values
    ]
    write_csv(config.data_dir / "equipment_tree.csv", TREE_FIELDS, nodes)
    write_csv(config.data_dir / "document_register.csv", DOC_FIELDS, docs)
    write_csv(config.data_dir / "required_docs.csv", REQUIRED_FIELDS, required)
    write_csv(config.data_dir / "injected_errors.csv", TRUTH_FIELDS, truth)
    manifest = dict(
        synthetic=True,
        seed=config.seed,
        as_of_date=config.as_of_date.isoformat(),
        systems=config.systems,
        subsystems=config.subsystems,
        equipment=config.equipment,
        baseline_documents=config.documents,
        document_count=len(docs),
        injection_events=event_number,
        expected_findings=len(truth),
        errors_per_type=config.errors_per_type,
        note="Fictional generated metadata only; no real drawings, files, ship or company data.",
    )
    write_json(config.data_dir / "manifest.json", manifest)
    (config.data_dir / "README.md").write_text(
        "# Synthetic data\n\nAll records are fictional and generated by `doctree generate`. "
        "They are not ship or Seaspan data. Refer to manifest.json for the seed and counts.\n\n"
        "The first word of each equipment name identifies its synthetic equipment class. "
        "required_docs.csv lists the required types for each class. row_id is a stable source "
        "record identifier, independent of the document ID and revision. injected_errors.csv "
        "records mutations and their expected consequences; multiple rows can describe "
        "the consequences of the same injection. File names are metadata; no PDFs exist.\n",
        encoding="utf-8",
    )
    return manifest
