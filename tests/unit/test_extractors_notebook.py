from __future__ import annotations

import json
from pathlib import Path

from src.core.extractors.notebook import extract_ipynb


def test_extract_ipynb_markdown_and_code_cells(tmp_path: Path) -> None:
    notebook = {
        "cells": [
            {"cell_type": "markdown", "source": ["Hello notebook"]},
            {
                "cell_type": "code",
                "source": ["print(1)"],
                "outputs": [{"output_type": "stream", "text": ["1\n", "2\n"]}],
            },
        ],
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
    }
    path = tmp_path / "sample.ipynb"
    path.write_text(json.dumps(notebook), encoding="utf-8")

    text = extract_ipynb(path)

    assert "Cell 1 (markdown)" in text
    assert "Hello notebook" in text
    assert "Cell 2 (code)" in text
    assert "print(1)" in text
    assert "1" in text


def test_extract_ipynb_caps_stream_output(tmp_path: Path) -> None:
    lines = [f"line-{index}\n" for index in range(50)]
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["x = 1"],
                "outputs": [{"output_type": "stream", "text": lines}],
            }
        ],
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
    }
    path = tmp_path / "long-output.ipynb"
    path.write_text(json.dumps(notebook), encoding="utf-8")

    text = extract_ipynb(path, output_lines=5)

    assert "line-4" in text
    assert "output truncated" in text
    assert "line-40" not in text
