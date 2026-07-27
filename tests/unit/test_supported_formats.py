from __future__ import annotations

from src.core.supported_formats import (
    SUPPORTED_EXTENSIONS,
    TABULAR_EXTENSIONS,
    TEXT_CODE_EXTENSIONS,
    VISION_EXTENSIONS,
    is_supported,
)


def test_supported_extensions_include_core_types() -> None:
    assert ".pdf" in SUPPORTED_EXTENSIONS
    assert ".csv" in TABULAR_EXTENSIONS
    assert ".py" in TEXT_CODE_EXTENSIONS
    assert ".png" in VISION_EXTENSIONS


def test_is_supported_without_vision_blocks_images() -> None:
    assert is_supported(".txt") is True
    assert is_supported(".png") is False
    assert is_supported(".png", vision_enabled=True) is True


def test_is_supported_normalizes_extension() -> None:
    assert is_supported("CSV") is True
    assert is_supported("csv") is True
