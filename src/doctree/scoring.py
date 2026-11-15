"""Score stable finding identities, including all false positives and false negatives."""

from collections import Counter

from doctree.models import RULES, Issue


def score(issues: list[Issue], changes: list[dict], truth: list[dict]) -> dict:
    expected_keys = [(r["rule"], r["entity_type"], r["entity_id"]) for r in truth]
    if any(not all(key) for key in expected_keys):
        raise ValueError("Ground truth requires a rule, entity type and entity identity")
    if any(rule not in RULES for rule, _, _ in expected_keys):
        raise ValueError("Ground truth contains an unknown rule")
    if any(count > 1 for count in Counter(expected_keys).values()):
        raise ValueError("Ground truth repeats a finding identity")
    expected = set(expected_keys)
    predicted = {(i.rule, i.entity_type, i.entity_id) for i in issues}
    predicted |= {("safe_normalization", "change", f"{c['row_id']}|{c['field']}") for c in changes}
    if any(not all(key) or key[0] not in RULES for key in predicted):
        raise ValueError("Predictions require registered rules and nonempty finding identities")

    def metrics(actual: set, wanted: set) -> dict:
        tp, fp, fn = len(actual & wanted), len(actual - wanted), len(wanted - actual)
        return dict(
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            support=len(wanted),
            predictions=len(actual),
            precision=tp / (tp + fp) if tp + fp else None,
            recall=tp / (tp + fn) if tp + fn else None,
        )

    return dict(
        synthetic=True,
        method="Exact match on (rule, entity_type, entity_id), unique findings; no true negatives",
        caveat=(
            "Scores measure recovery of controlled synthetic faults, including logged cascades. "
            "Near-title scores measure candidate retrieval, not verified duplicate content. "
            "Rules with no injected examples have null recall, not perfect recall."
        ),
        overall=metrics(predicted, expected),
        per_rule={
            rule: metrics(
                {p for p in predicted if p[0] == rule}, {e for e in expected if e[0] == rule}
            )
            for rule in sorted(RULES)
        },
        false_positives=[
            dict(rule=r, entity_type=t, entity_id=e) for r, t, e in sorted(predicted - expected)
        ],
        false_negatives=[
            dict(rule=r, entity_type=t, entity_id=e) for r, t, e in sorted(expected - predicted)
        ],
    )
