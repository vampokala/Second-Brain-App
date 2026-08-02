from __future__ import annotations

from pathlib import Path

from src.core.extractors.code_text import extract_code_or_config


def test_extract_code_or_config_plain_python(tmp_path: Path) -> None:
    path = tmp_path / "main.py"
    path.write_text("print('hi')\n", encoding="utf-8")

    assert extract_code_or_config(path) == "print('hi')\n"


def test_extract_code_or_config_iac_prefix(tmp_path: Path) -> None:
    path = tmp_path / "main.tf"
    path.write_text('resource "aws_s3_bucket" "b" {}\n', encoding="utf-8")

    text = extract_code_or_config(path)

    assert text.startswith("IaC source:")
    assert 'resource "aws_s3_bucket"' in text
