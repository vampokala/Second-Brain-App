from __future__ import annotations

from pathlib import Path

from src.core.extractors.tabular import extract_csv


def test_extract_csv_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")

    assert extract_csv(path) == ""


def test_extract_csv_simple_rows(tmp_path: Path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")

    text = extract_csv(path)

    assert "1\t2" in text
    assert "3\t4" in text
