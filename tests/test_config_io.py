from pathlib import Path

import pytest
import yaml

from doctree.config import load_config
from doctree.io import read_csv


def raw_config():
    return yaml.safe_load((Path(__file__).parents[1] / "configs/default.yaml").read_text())


def test_config_paths_independent_of_working_directory(tmp_path, monkeypatch):
    folder = tmp_path / "project" / "configs"
    folder.mkdir(parents=True)
    path = folder / "default.yaml"
    path.write_text(yaml.safe_dump(raw_config()))
    monkeypatch.chdir(tmp_path)
    config = load_config(path)
    assert config.data_dir == tmp_path / "project" / "data"
    assert config.reports_dir == tmp_path / "project" / "reports"


@pytest.mark.parametrize(
    ("section", "field", "value"),
    [
        ("validation", "title_similarity_threshold", 0),
        ("validation", "title_similarity_threshold", 1.1),
        ("validation", "filename_template", "{title}.pdf"),
        ("validation", "doc_types", ["manual"]),
        ("validation", "statuses", ["approved"]),
        ("validation", "required_by_class", {"pump": ["unknown"]}),
        ("validation", "required_by_class", {"pump unit": ["manual"]}),
        ("validation", "required_by_class", {7: ["manual"]}),
        ("validation", "required_by_class", ["pump"]),
        ("generation", "errors_per_type", -1),
        ("generation", "equipment", 0),
        ("generation", "documents", 1),
    ],
)
def test_invalid_configuration_rejected(tmp_path, section, field, value):
    raw = raw_config()
    raw[section][field] = value
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError):
        load_config(path)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "a,a\n1,2\n",
        "b\n1\n",
        "a,b\n1\n",
        "a,b\n1,2,3\n",
    ],
)
def test_malformed_csv_or_missing_schema_rejected(tmp_path, content):
    path = tmp_path / "bad.csv"
    path.write_text(content)
    with pytest.raises(ValueError):
        read_csv(path, ["a", "b"])


def test_utf8_bom_csv_accepted(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text("\ufeffa,b\n1,2\n")
    assert read_csv(path, ["a", "b"]) == [{"a": "1", "b": "2"}]


def test_malformed_yaml_rejected_with_configuration_error(tmp_path):
    path = tmp_path / "invalid.yaml"
    path.write_text("generation: [\n")
    with pytest.raises(ValueError, match="Invalid YAML"):
        load_config(path)
