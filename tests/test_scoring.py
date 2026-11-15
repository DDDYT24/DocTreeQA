import pytest

from doctree.models import Issue
from doctree.scoring import score


def finding(row):
    return Issue("error", "missing_title", "SYN-X", "P-1", "Missing", "Confirm", "row", row)


def truth(row, rule="missing_title", entity_type="row"):
    return dict(rule=rule, entity_type=entity_type, entity_id=row)


def test_precision_recall_include_false_positives_and_false_negatives():
    result = score([finding("A"), finding("B")], [], [truth("A"), truth("C"), truth("D")])
    values = result["per_rule"]["missing_title"]
    assert values["true_positives"] == 1
    assert values["false_positives"] == 1
    assert values["false_negatives"] == 2
    assert values["precision"] == 0.5
    assert values["recall"] == pytest.approx(1 / 3)
    assert result["false_positives"] == [truth("B")]
    assert result["false_negatives"] == [truth("C"), truth("D")]


def test_no_support_is_not_perfect_recall():
    values = score([], [], [])["per_rule"]["tree_cycle"]
    assert values["recall"] is None
    assert values["precision"] is None


def test_duplicate_predictions_do_not_inflate_scores():
    result = score([finding("A"), finding("A")], [], [truth("A")])
    assert result["overall"]["true_positives"] == 1


def test_changes_scored_on_stable_row_and_field():
    result = score(
        [], [dict(row_id="A", field="title")], [truth("A|title", "safe_normalization", "change")]
    )
    assert result["overall"]["precision"] == 1
    assert result["overall"]["recall"] == 1


def test_missed_findings_have_zero_recall_and_undefined_precision():
    values = score([], [], [truth("A")])["overall"]
    assert values["recall"] == 0
    assert values["precision"] is None


def test_unexpected_findings_have_zero_precision_and_undefined_recall():
    values = score([finding("A")], [], [])["overall"]
    assert values["precision"] == 0
    assert values["recall"] is None


def test_invalid_prediction_identities_rejected():
    with pytest.raises(ValueError, match="Predictions"):
        score([finding("")], [], [])


@pytest.mark.parametrize(
    "rows",
    [
        [truth("A"), truth("A")],
        [truth("A", "misspelled_rule")],
        [truth("")],
    ],
)
def test_broken_ground_truth_rejected(rows):
    with pytest.raises(ValueError):
        score([], [], rows)
