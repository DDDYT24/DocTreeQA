"""Stable finding identities shared by exports and the independent scorer."""

from dataclasses import asdict, dataclass

REQUIRED_METADATA = (
    "doc_id",
    "title",
    "doc_type",
    "revision",
    "status",
    "issue_date",
    "file_name",
    "page_count",
)
RULES = frozenset(
    {
        *(f"missing_{field}" for field in REQUIRED_METADATA),
        "tree_duplicate_code",
        "tree_missing_code",
        "tree_missing_name",
        "tree_invalid_parent",
        "tree_cycle",
        "tree_level",
        "unknown_equipment",
        "unmapped_document",
        "ambiguous_equipment",
        "wrong_mapping_level",
        "invalid_doc_type",
        "invalid_status",
        "invalid_revision",
        "invalid_date",
        "future_date",
        "invalid_page_count",
        "filename_mismatch",
        "duplicate_doc_id",
        "exact_duplicate",
        "duplicate_file",
        "near_duplicate_title",
        "multiple_issued",
        "superseded_without_replacement",
        "missing_required",
        "unknown_equipment_class",
        "safe_normalization",
    }
)


@dataclass(frozen=True)
class Issue:
    severity: str
    rule: str
    doc_id: str
    equipment_code: str
    message: str
    suggested_action: str
    entity_type: str
    entity_id: str
    row_id: str = ""
    system_code: str = ""
    subsystem_code: str = ""
    review_status: str = "Open"

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationResult:
    documents: list[dict[str, str]]
    issues: list[Issue]
    changes: list[dict[str, str]]
    completeness: list[dict]
    tree_trustworthy: bool
