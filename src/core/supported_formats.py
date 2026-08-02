"""Single source of truth for ingest-supported file extensions."""

from __future__ import annotations

SUPPORTED_EXTENSIONS = frozenset(
    {
        ".pdf",
        ".docx",
        ".txt",
        ".md",
        ".html",
        ".csv",
        ".tsv",
        ".xlsx",
        ".xlsm",
        ".pptx",
        ".ipynb",
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".java",
        ".rs",
        ".rb",
        ".kt",
        ".swift",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",
        ".c",
        ".cs",
        ".scala",
        ".php",
        ".sh",
        ".bash",
        ".ps1",
        ".sql",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".tf",
        ".hcl",
        ".prisma",
        # vision gated separately
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }
)

TEXT_CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".java",
        ".rs",
        ".rb",
        ".kt",
        ".swift",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",
        ".c",
        ".cs",
        ".scala",
        ".php",
        ".sh",
        ".bash",
        ".ps1",
        ".sql",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".tf",
        ".hcl",
        ".prisma",
    }
)

TABULAR_EXTENSIONS = frozenset({".csv", ".tsv", ".xlsx", ".xlsm"})

VISION_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})

_IAC_EXTENSIONS = frozenset({".tf", ".hcl"})


def _normalize_ext(ext: str) -> str:
    normalized = ext.lower()
    if not normalized.startswith("."):
        normalized = f".{normalized}"
    return normalized


def is_supported(ext: str, *, vision_enabled: bool = False) -> bool:
    """Return True when *ext* is ingestable under the given vision setting."""
    normalized = _normalize_ext(ext)
    if normalized in VISION_EXTENSIONS:
        return vision_enabled
    return normalized in SUPPORTED_EXTENSIONS


def is_vision_extension(ext: str) -> bool:
    return _normalize_ext(ext) in VISION_EXTENSIONS


def is_iac_extension(ext: str) -> bool:
    return _normalize_ext(ext) in _IAC_EXTENSIONS
