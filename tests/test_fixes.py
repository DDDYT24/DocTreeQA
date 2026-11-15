from copy import deepcopy

from doctree.fixes import normalize
from doctree.validation import validate


def test_only_safe_changes_are_made_and_logged(sample):
    _, docs, _ = sample
    docs[1].update(title="  Pump manual  ", doc_type=" MANUAL ", revision="???", status="ISSUED")
    before = deepcopy(docs)
    cleaned, changes = normalize(docs)
    assert docs == before
    assert cleaned[1]["revision"] == "???"
    assert cleaned[1]["status"] == "ISSUED"
    assert cleaned[1]["title"] == "Pump manual"
    assert cleaned[1]["doc_type"] == "manual"
    assert changes == [
        dict(
            row_id="ROW-2",
            doc_id="SYN-M",
            field="title",
            before="  Pump manual  ",
            after="Pump manual",
            reason="Trim surrounding whitespace; lowercase doc_type only",
        ),
        dict(
            row_id="ROW-2",
            doc_id="SYN-M",
            field="doc_type",
            before=" MANUAL ",
            after="manual",
            reason="Trim surrounding whitespace; lowercase doc_type only",
        ),
    ]


def test_normalization_is_idempotent(sample):
    _, docs, _ = sample
    docs[1]["doc_type"] = " MANUAL "
    cleaned, changes = normalize(docs)
    second, second_changes = normalize(cleaned)
    assert cleaned == second
    assert changes
    assert second_changes == []


def test_safe_normalization_passes_validation(config, sample):
    tree, docs, required = sample
    docs[1]["doc_type"] = " MANUAL "
    result = validate(tree, docs, required, config)
    assert len(result.changes) == 1
    assert result.issues == []
