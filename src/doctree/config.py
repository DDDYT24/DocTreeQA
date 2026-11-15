"""Load reproducible settings; resolve paths relative to the project, not the shell."""

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Formatter

import yaml


@dataclass(frozen=True)
class Config:
    root: Path
    seed: int
    as_of_date: date
    systems: int
    subsystems: int
    equipment: int
    documents: int
    errors_per_type: int
    title_similarity_threshold: float
    filename_template: str
    doc_types: tuple[str, ...]
    statuses: tuple[str, ...]
    required_by_class: dict[str, tuple[str, ...]]
    data_dir: Path
    reports_dir: Path


def load_config(path: str | Path) -> Config:
    path = Path(path).resolve()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Configuration must be a YAML mapping")
    try:
        gen, val, paths = raw["generation"], raw["validation"], raw["paths"]
        root = path.parent.parent
        config = Config(
            root=root,
            seed=int(raw["seed"]),
            as_of_date=date.fromisoformat(str(raw["as_of_date"])),
            **{
                name: int(gen[name])
                for name in ("systems", "subsystems", "equipment", "documents", "errors_per_type")
            },
            title_similarity_threshold=float(val["title_similarity_threshold"]),
            filename_template=str(val["filename_template"]),
            doc_types=tuple(val["doc_types"]),
            statuses=tuple(val["statuses"]),
            required_by_class={k: tuple(v) for k, v in val["required_by_class"].items()},
            data_dir=(root / paths["data_dir"]).resolve(),
            reports_dir=(root / paths["reports_dir"]).resolve(),
        )
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"Invalid configuration structure: {exc}") from exc
    if not 0 < config.title_similarity_threshold <= 1:
        raise ValueError("title_similarity_threshold must be in (0, 1]")
    if not 1 <= config.systems <= config.subsystems <= config.equipment:
        raise ValueError("Require 1 <= systems <= subsystems <= equipment")
    if config.documents < config.equipment * len(config.doc_types):
        raise ValueError("documents must allow an issued document of every type per equipment")
    if config.errors_per_type < 0:
        raise ValueError("errors_per_type cannot be negative")
    required_types = {"manual", "datasheet", "drawing", "test_report", "spares_list"}
    if set(config.doc_types) != required_types or len(config.doc_types) != len(required_types):
        raise ValueError("doc_types must contain the supported types exactly once")
    if set(config.statuses) != {"draft", "issued", "superseded"}:
        raise ValueError("statuses must contain draft, issued, superseded")
    if not config.required_by_class or any(
        not isinstance(key, str)
        or not key
        or not key.isidentifier()
        or key != key.strip().lower()
        or not values
        or len(set(values)) != len(values)
        or not set(values) <= required_types
        for key, values in config.required_by_class.items()
    ):
        raise ValueError("Equipment classes must have unique, supported required document types")
    fields = {field for _, field, _, _ in Formatter().parse(config.filename_template) if field}
    if fields != {"doc_id", "revision"}:
        raise ValueError("filename_template must use only {doc_id} and {revision}, both required")
    return config
