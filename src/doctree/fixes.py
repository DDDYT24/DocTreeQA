"""Only whitespace trimming and document type case normalization are automatic."""

from doctree.io import DOC_FIELDS

CHANGE_FIELDS = ["row_id", "doc_id", "field", "before", "after", "reason"]


def normalize(documents: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    cleaned, changes = [], []
    for source in documents:
        row = dict(source)
        for field in DOC_FIELDS:
            if field == "row_id":
                continue
            before = row[field]
            after = before.strip()
            if field == "doc_type":
                after = after.lower()
            if before != after:
                changes.append(
                    dict(
                        row_id=source["row_id"],
                        doc_id=source["doc_id"].strip(),
                        field=field,
                        before=before,
                        after=after,
                        reason="Trim surrounding whitespace; lowercase doc_type only",
                    )
                )
                row[field] = after
        cleaned.append(row)
    return cleaned, changes
