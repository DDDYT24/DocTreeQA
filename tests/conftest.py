from dataclasses import replace
from pathlib import Path

import pytest

from doctree.config import load_config
from doctree.io import DOC_FIELDS, REQUIRED_FIELDS, TREE_FIELDS, read_csv


@pytest.fixture
def config(tmp_path):
    base = load_config(Path(__file__).parents[1] / "configs/default.yaml")
    return replace(
        base, root=tmp_path, data_dir=tmp_path / "data", reports_dir=tmp_path / "reports"
    )


@pytest.fixture
def sample():
    folder = Path(__file__).parent / "fixtures"
    return (
        read_csv(folder / "equipment_tree.csv", TREE_FIELDS),
        read_csv(folder / "document_register.csv", DOC_FIELDS),
        read_csv(folder / "required_docs.csv", REQUIRED_FIELDS),
    )
