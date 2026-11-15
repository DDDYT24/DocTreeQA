"""Pure detectors. This module never reads the injected-error ground truth."""

import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from difflib import SequenceMatcher

from doctree.config import Config
from doctree.fixes import normalize
from doctree.io import DOC_FIELDS
from doctree.models import REQUIRED_METADATA, RULES, Issue, ValidationResult


def revision_number(value: str) -> int | None:
    return int(value) if re.fullmatch(r"[0-9]+", value) else None


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", value).split())


def validate(
    tree: list[dict[str, str]],
    documents: list[dict[str, str]],
    required: list[dict[str, str]],
    config: Config,
) -> ValidationResult:
    ids = [d["row_id"] for d in documents]
    if any(not value.strip() for value in ids) or len(ids) != len(set(ids)):
        raise ValueError("row_id must be nonempty and unique; it is the source record identity")
    documents, changes = normalize(documents)
    issues: dict[tuple[str, str, str], Issue] = {}
    nodes = {}
    for node in tree:
        if node["code"]:
            nodes.setdefault(node["code"], node)
    node_counts = Counter(n["code"] for n in tree)

    def ancestors(code: str) -> list[dict]:
        chain, seen = [], set()
        while code in nodes and code not in seen:
            seen.add(code)
            node = nodes[code]
            chain.append(node)
            code = node["parent_code"]
        return chain

    def add(
        rule: str,
        message: str,
        action: str,
        *,
        row: dict | None = None,
        entity_type: str = "row",
        entity_id: str = "",
        equipment_code: str = "",
        severity: str = "error",
        doc_id: str = "",
    ) -> None:
        if rule not in RULES:
            raise ValueError(f"Unregistered rule: {rule}")
        row = row or {}
        equipment_code = equipment_code or row.get("equipment_code", "")
        chain = ancestors(equipment_code)
        finding = Issue(
            severity=severity,
            rule=rule,
            doc_id=doc_id or row.get("doc_id", ""),
            equipment_code=equipment_code,
            message=message,
            suggested_action=action,
            entity_type=entity_type,
            entity_id=entity_id or row.get("row_id", ""),
            row_id=row.get("row_id", ""),
            system_code=next((n["code"] for n in chain if n["level"] == "System"), ""),
            subsystem_code=next((n["code"] for n in chain if n["level"] == "Subsystem"), ""),
        )
        issues[(rule, entity_type, finding.entity_id)] = finding

    def tree_issue(rule: str, node: dict, index: int, message: str) -> None:
        add(
            rule,
            message,
            "Correct the tree source after confirming the intended hierarchy",
            entity_type="node",
            entity_id=node["code"] or f"@row:{index}",
            equipment_code=node["code"],
        )

    expected_parent = {"System": None, "Subsystem": "System", "Equipment": "Subsystem"}
    for index, node in enumerate(tree, start=1):
        code, parent, level = node["code"], node["parent_code"], node["level"]
        if not code.strip():
            tree_issue("tree_missing_code", node, index, "Tree node has no code")
        if not node["name"].strip():
            tree_issue("tree_missing_name", node, index, "Tree node has no name")
        if node_counts[code] > 1:
            tree_issue("tree_duplicate_code", node, index, "Tree code identifies multiple nodes")
        if parent and parent not in nodes or level in {"Subsystem", "Equipment"} and not parent:
            tree_issue("tree_invalid_parent", node, index, "Node has no valid parent")
        if (
            level not in expected_parent
            or (level == "System" and parent)
            or (
                level in {"Subsystem", "Equipment"}
                and parent in nodes
                and nodes[parent]["level"] != expected_parent[level]
            )
        ):
            tree_issue("tree_level", node, index, "Node level and parent level are inconsistent")
    # Iterative traversal remains bounded for self loops, longer cycles, and broken parents.
    cycle_nodes = set()
    for code in nodes:
        trail, positions = [], {}
        while code in nodes:
            if code in positions:
                cycle_nodes.update(trail[positions[code] :])
                break
            positions[code] = len(trail)
            trail.append(code)
            code = nodes[code]["parent_code"]
    for code in sorted(cycle_nodes):
        add(
            "tree_cycle",
            "Node participates in a parent cycle",
            "Repair the parent cycle",
            entity_type="node",
            entity_id=code,
            equipment_code=code,
        )

    for row in documents:
        for field in REQUIRED_METADATA:
            if not row[field]:
                add(
                    f"missing_{field}",
                    f"Required metadata {field} is empty",
                    f"Confirm {field} from the source document",
                    row=row,
                )
        code = row["equipment_code"]
        if not code:
            add(
                "unmapped_document",
                "Document has no equipment mapping",
                "Select one equipment node after reviewing the document",
                row=row,
            )
        elif code not in nodes:
            add(
                "unknown_equipment",
                "Equipment code does not exist in the tree",
                "Confirm the code or add an approved tree node",
                row=row,
            )
        elif node_counts[code] > 1:
            add(
                "ambiguous_equipment",
                "Equipment code matches multiple tree nodes",
                "Resolve the duplicate tree code before mapping",
                row=row,
            )
        elif nodes[code]["level"] != "Equipment":
            add(
                "wrong_mapping_level",
                "Document is mapped above the equipment level",
                "Select the intended equipment node",
                row=row,
            )
        for field, allowed, rule in (
            ("doc_type", config.doc_types, "invalid_doc_type"),
            ("status", config.statuses, "invalid_status"),
        ):
            if row[field] and row[field] not in allowed:
                add(
                    rule,
                    f"Unsupported {field}: {row[field]}",
                    "Confirm the value; do not guess a replacement",
                    row=row,
                )
        revision = revision_number(row["revision"])
        if row["revision"] and revision is None:
            add(
                "invalid_revision",
                "Revision must be a nonnegative integer",
                "Confirm the revision convention or source revision",
                row=row,
            )
        if row["page_count"] and (
            not re.fullmatch(r"[0-9]+", row["page_count"]) or int(row["page_count"]) <= 0
        ):
            add(
                "invalid_page_count",
                "Page count must be a positive integer",
                "Confirm the page count from the actual document",
                row=row,
            )
        if row["issue_date"]:
            try:
                if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", row["issue_date"]):
                    raise ValueError("Expected YYYY-MM-DD")
                issued_on = date.fromisoformat(row["issue_date"])
            except ValueError:
                add(
                    "invalid_date",
                    "Issue date is not a valid YYYY-MM-DD date",
                    "Confirm the date from the source document",
                    row=row,
                )
            else:
                if issued_on > config.as_of_date:
                    add(
                        "future_date",
                        "Issue date is later than the configured review date",
                        "Confirm the issue date or the intended review date",
                        row=row,
                    )
        if row["file_name"] and row["doc_id"] and revision is not None:
            expected = config.filename_template.format(**row)
            if row["file_name"] != expected:
                add(
                    "filename_mismatch",
                    f"Expected file name {expected}",
                    "Check the actual file and confirm which metadata is correct",
                    row=row,
                )

    by_doc = defaultdict(list)
    seen_revisions, seen_rows, seen_files = {}, {}, {}
    title_candidates = defaultdict(list)
    for row in documents:
        doc_id, revision = row["doc_id"], revision_number(row["revision"])
        if doc_id:
            by_doc[doc_id].append(row)
        if doc_id and revision is not None:
            key = (doc_id, revision)
            if key in seen_revisions:
                add(
                    "duplicate_doc_id",
                    f"Document and revision also occur at {seen_revisions[key]}",
                    "Review the records together; retain the authoritative record",
                    row=row,
                )
            else:
                seen_revisions[key] = row["row_id"]
        signature = tuple(row[field] for field in DOC_FIELDS if field != "row_id")
        if signature in seen_rows:
            add(
                "exact_duplicate",
                f"Metadata exactly duplicates row {seen_rows[signature]}",
                "Review duplicate records; do not automatically delete them",
                row=row,
                severity="warning",
            )
        else:
            seen_rows[signature] = row["row_id"]
        if row["file_name"] and doc_id:
            first = seen_files.setdefault(row["file_name"], row)
            if first["doc_id"] != doc_id:
                add(
                    "duplicate_file",
                    f"File name is also registered under {first['doc_id']}",
                    "Inspect the actual files; a shared name does not prove identical content",
                    row=row,
                    severity="warning",
                )
        title = normalized_title(row["title"])
        # Block on equipment and type: shared technical wording across equipment is normal.
        group = (row["equipment_code"], row["doc_type"])
        if title and doc_id and row["doc_type"] in config.doc_types and group[0] in nodes:
            candidates = title_candidates[group]
            for other_id, other_title, other_row in candidates:
                if other_id == doc_id:
                    continue
                similarity = SequenceMatcher(None, title, other_title, autojunk=False).ratio()
                if similarity >= config.title_similarity_threshold:
                    add(
                        "near_duplicate_title",
                        f"Title similarity {similarity:.3f} to row {other_row}; manual review only",
                        "Compare the documents and accept or reject this candidate",
                        row=row,
                        severity="warning",
                    )
                    break
            if (doc_id, title) not in {(c[0], c[1]) for c in candidates}:
                candidates.append((doc_id, title, row["row_id"]))

    for doc_id, revisions in by_doc.items():
        issued = {
            revision_number(row["revision"])
            for row in revisions
            if row["status"] == "issued" and revision_number(row["revision"]) is not None
        }
        if len(issued) > 1:
            add(
                "multiple_issued",
                "More than one revision is marked issued",
                "Confirm the current revision and update obsolete statuses",
                row=revisions[0],
                entity_type="document",
                entity_id=doc_id,
            )
        for row in revisions:
            revision = revision_number(row["revision"])
            if (
                row["status"] == "superseded"
                and revision is not None
                and not any(newer > revision for newer in issued)
            ):
                add(
                    "superseded_without_replacement",
                    "No provably newer issued revision exists",
                    "Locate the replacement or confirm the revision and status",
                    row=row,
                )

    required_by_class: dict[str, set[str]] = defaultdict(set)
    for rule in required:
        equipment_class, doc_type = rule["equipment_class"], rule["doc_type"]
        if not equipment_class or equipment_class != equipment_class.strip().lower():
            raise ValueError("Required document classes must be nonempty lowercase names")
        if doc_type not in config.doc_types:
            raise ValueError(f"Unsupported required document type: {doc_type}")
        if doc_type in required_by_class[equipment_class]:
            raise ValueError(f"Duplicate required document rule: {equipment_class}/{doc_type}")
        required_by_class[equipment_class].add(doc_type)
    if not required_by_class:
        raise ValueError("required_docs.csv must define at least one equipment class")

    present = defaultdict(set)
    for row in documents:
        code = row["equipment_code"]
        if (
            code in nodes
            and node_counts[code] == 1
            and nodes[code]["level"] == "Equipment"
            and row["status"] == "issued"
            and row["doc_type"] in config.doc_types
        ):
            present[code].add(row["doc_type"])
    totals = {code: [0, 0] for code in nodes}
    missing_by_equipment = {}
    for code, node in nodes.items():
        if node["level"] != "Equipment":
            continue
        words = node["name"].split()
        equipment_class = words[0].lower() if words else ""
        if equipment_class not in required_by_class:
            add(
                "unknown_equipment_class",
                "Equipment name has no recognized class prefix",
                "Confirm the equipment class and its required document rules",
                entity_type="node",
                entity_id=code,
                equipment_code=code,
            )
            continue
        needed = required_by_class[equipment_class]
        missing = needed - present[code]
        missing_by_equipment[code] = sorted(missing)
        for doc_type in sorted(missing):
            add(
                "missing_required",
                f"No issued {doc_type} is registered for this equipment",
                "Locate the required document or obtain an approved exception",
                entity_type="requirement",
                entity_id=f"{code}|{doc_type}",
                equipment_code=code,
            )
        for ancestor in ancestors(code):
            totals[ancestor["code"]][0] += len(needed)
            totals[ancestor["code"]][1] += len(needed) - len(missing)
    completeness = []
    for code, node in nodes.items():
        required_count, present_count = totals[code]
        completeness.append(
            dict(
                **node,
                equipment_class=(
                    node["name"].split()[0].lower()
                    if node["level"] == "Equipment" and node["name"].split()
                    else ""
                ),
                required_count=required_count,
                present_count=present_count,
                missing_count=required_count - present_count,
                completeness_pct=round(100 * present_count / required_count, 4)
                if required_count
                else None,
                missing_types=";".join(missing_by_equipment.get(code, [])),
            )
        )
    return ValidationResult(
        documents=documents,
        issues=list(issues.values()),
        changes=changes,
        completeness=completeness,
        tree_trustworthy=not any(
            i.rule.startswith("tree_") or i.rule == "unknown_equipment_class"
            for i in issues.values()
        ),
    )
