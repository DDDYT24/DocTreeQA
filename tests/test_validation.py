from dataclasses import replace

import pytest

from doctree.models import REQUIRED_METADATA
from doctree.validation import validate


def rule_set(result):
    return {issue.rule for issue in result.issues}


def test_handmade_clean_fixture_passes_all_checks(config, sample):
    result = validate(*sample, config)
    assert not result.issues
    assert not result.changes
    assert result.tree_trustworthy
    assert all(row["completeness_pct"] == 100 for row in result.completeness)


@pytest.mark.parametrize("field", REQUIRED_METADATA)
@pytest.mark.parametrize("missing", [False, True])
def test_required_metadata_passing_and_failing(config, sample, field, missing):
    tree, docs, required = sample
    if missing:
        docs[1][field] = ""
    result = validate(tree, docs, required, config)
    assert (f"missing_{field}" in rule_set(result)) is missing


@pytest.mark.parametrize(
    ("field", "value", "rule"),
    [
        ("equipment_code", "", "unmapped_document"),
        ("equipment_code", "DOES-NOT-EXIST", "unknown_equipment"),
        ("equipment_code", "S", "wrong_mapping_level"),
        ("doc_type", "unknown", "invalid_doc_type"),
        ("status", "ISSUED", "invalid_status"),
        ("revision", "R2", "invalid_revision"),
        ("page_count", "0", "invalid_page_count"),
        ("page_count", "-1", "invalid_page_count"),
        ("page_count", "2.5", "invalid_page_count"),
        ("issue_date", "2026-02-30", "invalid_date"),
        ("issue_date", "20260101", "invalid_date"),
        ("issue_date", "2026-1-1", "invalid_date"),
        ("issue_date", "2026-11-15", "future_date"),
        ("file_name", "incorrect.pdf", "filename_mismatch"),
    ],
)
@pytest.mark.parametrize("broken", [False, True])
def test_metadata_and_mapping_rules(config, sample, field, value, rule, broken):
    tree, docs, required = sample
    if broken:
        docs[1][field] = value
    assert (rule in rule_set(validate(tree, docs, required, config))) is broken


def test_review_date_boundary_and_valid_leap_date(config, sample):
    tree, docs, required = sample
    docs[1]["issue_date"] = config.as_of_date.isoformat()
    docs[2]["issue_date"] = "2024-02-29"
    assert not validate(tree, docs, required, config).issues


@pytest.mark.parametrize(
    ("mutation", "rule"),
    [
        ("duplicate", "tree_duplicate_code"),
        ("empty_code", "tree_missing_code"),
        ("empty_name", "tree_missing_name"),
        ("orphan", "tree_invalid_parent"),
        ("no_parent", "tree_invalid_parent"),
        ("wrong_level", "tree_level"),
        ("unknown_level", "tree_level"),
        ("system_parent", "tree_level"),
        ("cycle", "tree_cycle"),
        ("self_cycle", "tree_cycle"),
    ],
)
@pytest.mark.parametrize("broken", [False, True])
def test_tree_rules(config, sample, mutation, rule, broken):
    tree, docs, required = sample
    if broken:
        if mutation == "duplicate":
            tree.append(dict(tree[-1]))
        elif mutation == "empty_code":
            tree[-1]["code"] = ""
        elif mutation == "empty_name":
            tree[-1]["name"] = ""
        elif mutation == "orphan":
            tree[-1]["parent_code"] = "UNKNOWN"
        elif mutation == "no_parent":
            tree[-1]["parent_code"] = ""
        elif mutation == "wrong_level":
            tree[-1]["parent_code"] = "S"
        elif mutation == "unknown_level":
            tree[-1]["level"] = "Component"
        elif mutation == "system_parent":
            tree[0]["parent_code"] = "SS"
        elif mutation == "cycle":
            tree[0]["parent_code"] = "P-1"
        elif mutation == "self_cycle":
            tree[-1]["parent_code"] = "P-1"
    result = validate(tree, docs, required, config)
    assert (rule in rule_set(result)) is broken
    assert result.tree_trustworthy is (not broken)


def test_ambiguous_equipment_mapping_is_not_silently_selected(config, sample):
    tree, docs, required = sample
    tree.append(dict(tree[-1]))
    result = validate(tree, docs, required, config)
    assert sum(i.rule == "ambiguous_equipment" for i in result.issues) == len(docs)
    assert not result.tree_trustworthy


def test_cycle_only_marks_cycle_participants(config, sample):
    tree, docs, required = sample
    tree[0]["parent_code"] = "SS"
    result = validate(tree, docs, required, config)
    assert {i.entity_id for i in result.issues if i.rule == "tree_cycle"} == {"S", "SS"}


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("exact", {"duplicate_doc_id", "exact_duplicate"}),
        ("conflicting", {"duplicate_doc_id"}),
        ("shared_file", {"duplicate_file", "filename_mismatch", "near_duplicate_title"}),
        ("similar_title", {"near_duplicate_title"}),
    ],
)
def test_duplicate_candidates_flagged_without_deletion(config, sample, mode, expected):
    tree, docs, required = sample
    clone = dict(docs[1], row_id="ROW-5")
    if mode == "conflicting":
        clone["page_count"] = "99"
    if mode in {"shared_file", "similar_title"}:
        clone["doc_id"] = "SYN-COPY"
    if mode == "similar_title":
        clone["title"] = "PUMP / UNIT / P-1 / MANUAL"
        clone["file_name"] = "SYN-COPY_R2.pdf"
    docs.append(clone)
    result = validate(tree, docs, required, config)
    assert rule_set(result) == expected
    assert len(result.documents) == len(docs)


def test_distinct_revisions_are_not_duplicate_ids(config, sample):
    result = validate(*sample, config)
    assert not {"duplicate_doc_id", "duplicate_file", "near_duplicate_title"} & rule_set(result)


def test_numerically_equal_revision_keys_detect_duplicates(config, sample):
    tree, docs, required = sample
    clone = dict(docs[1], row_id="ROW-5", revision="02", file_name="SYN-M_R02.pdf")
    docs.append(clone)
    result = validate(tree, docs, required, config)
    assert "duplicate_doc_id" in rule_set(result)
    assert "multiple_issued" not in rule_set(result)


def test_similarity_threshold_is_used(config, sample):
    tree, docs, required = sample
    clone = dict(
        docs[1],
        row_id="ROW-5",
        doc_id="OTHER",
        file_name="OTHER_R2.pdf",
        title="Pump Unit P-1 manual revised",
    )
    docs.append(clone)
    assert "near_duplicate_title" not in rule_set(
        validate(*sample, replace(config, title_similarity_threshold=1.0))
    )
    assert "near_duplicate_title" in rule_set(
        validate(*sample, replace(config, title_similarity_threshold=0.8))
    )


@pytest.mark.parametrize("same_equipment", [False, True])
def test_similarity_is_blocked_by_equipment(config, sample, same_equipment):
    tree, docs, required = sample
    tree.append(dict(tree[-1], code="P-2", name="Pump Unit P-2"))
    docs.append(
        dict(
            docs[1],
            row_id="ROW-5",
            doc_id="OTHER",
            file_name="OTHER_R2.pdf",
            equipment_code="P-1" if same_equipment else "P-2",
        )
    )
    result = validate(tree, docs, required, config)
    assert ("near_duplicate_title" in rule_set(result)) is same_equipment


@pytest.mark.parametrize("broken", [False, True])
def test_multiple_issued_revisions(config, sample, broken):
    tree, docs, required = sample
    if broken:
        docs[0]["status"] = "issued"
    assert ("multiple_issued" in rule_set(validate(tree, docs, required, config))) is broken


@pytest.mark.parametrize("replacement", ["newer", "equal", "older", "draft", "invalid"])
def test_superseded_requires_newer_issued_revision(config, sample, replacement):
    tree, docs, required = sample
    if replacement == "equal":
        docs[1].update(revision="1", file_name="SYN-M_R1.pdf")
    elif replacement == "older":
        docs[1].update(revision="0", file_name="SYN-M_R0.pdf")
    elif replacement == "draft":
        docs[1]["status"] = "draft"
    elif replacement == "invalid":
        docs[1]["revision"] = "unknown"
    result = validate(tree, docs, required, config)
    assert ("superseded_without_replacement" in rule_set(result)) is (replacement != "newer")


@pytest.mark.parametrize("missing", [False, True])
def test_completeness_counts_only_issued_documents(config, sample, missing):
    tree, docs, required = sample
    if missing:
        docs[1]["status"] = "draft"
    result = validate(tree, docs, required, config)
    assert ("missing_required" in rule_set(result)) is missing
    equipment = next(r for r in result.completeness if r["level"] == "Equipment")
    assert equipment["required_count"] == 3
    assert equipment["present_count"] == (2 if missing else 3)


def test_parent_rollup_is_weighted_by_requirements(config, sample):
    tree, docs, required = sample
    tree.append(dict(tree[-1], code="V-1", name="Valve Unit V-1"))
    required.append(dict(equipment_class="valve", doc_type="datasheet"))
    result = validate(tree, docs, required, config)
    summary = next(r for r in result.completeness if r["level"] == "System")
    assert summary["required_count"] == 4
    assert summary["present_count"] == 3
    assert summary["completeness_pct"] == 75


def test_missing_equipment_class_blocks_trustworthy_completeness(config, sample):
    tree, docs, required = sample
    tree[-1]["name"] = "Unknown Class"
    result = validate(tree, docs, required, config)
    assert "unknown_equipment_class" in rule_set(result)
    assert not result.tree_trustworthy
    assert result.completeness[-1]["completeness_pct"] is None


def test_empty_valid_tree_does_not_divide_by_zero(config, sample):
    _, _, required = sample
    result = validate([], [], required, config)
    assert result.completeness == []


@pytest.mark.parametrize("mode", ["duplicate", "blank"])
def test_invalid_source_identity_rejected(config, sample, mode):
    tree, docs, required = sample
    docs[1]["row_id"] = docs[0]["row_id"] if mode == "duplicate" else ""
    with pytest.raises(ValueError, match="row_id"):
        validate(tree, docs, required, config)


@pytest.mark.parametrize("mode", ["duplicate", "unknown_type", "uppercase_class", "empty"])
def test_broken_requirement_rules_rejected(config, sample, mode):
    tree, docs, required = sample
    if mode == "duplicate":
        required.append(dict(required[0]))
    elif mode == "unknown_type":
        required[0]["doc_type"] = "unknown"
    elif mode == "uppercase_class":
        required[0]["equipment_class"] = "PUMP"
    else:
        required = []
    with pytest.raises(ValueError):
        validate(tree, docs, required, config)
