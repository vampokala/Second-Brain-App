import os
import tempfile

import pytest
from src.core.document_processor import DocumentProcessor


@pytest.fixture
def processor():
    return DocumentProcessor(chunk_size=50, overlap=10)


def _write_temp_file(content: str, suffix: str) -> str:
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return f.name


class TestExtractText:
    def test_txt_extraction(self, processor):
        path = _write_temp_file("Hello world", ".txt")
        try:
            assert processor.extract_text(path) == "Hello world"
        finally:
            os.unlink(path)

    def test_md_extraction(self, processor):
        path = _write_temp_file("# Title\nSome content", ".md")
        try:
            text = processor.extract_text(path)
            assert "Title" in text
            assert "Some content" in text
        finally:
            os.unlink(path)

    def test_html_extraction(self, processor):
        path = _write_temp_file("<html><body><p>Hello HTML</p></body></html>", ".html")
        try:
            text = processor.extract_text(path)
            assert "Hello HTML" in text
        finally:
            os.unlink(path)

    def test_csv_extraction(self, processor):
        path = _write_temp_file("a,b\n1,2\n", ".csv")
        try:
            text = processor.extract_text(path)
            assert "1" in text
            assert "2" in text
        finally:
            os.unlink(path)

    def test_unsupported_format_raises(self, processor):
        path = _write_temp_file("data", ".xyz")
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                processor.extract_text(path)
        finally:
            os.unlink(path)


class TestCleanText:
    def test_collapses_whitespace(self, processor):
        assert processor.clean_text("hello   \n\t world") == "hello world"

    def test_strips_leading_trailing(self, processor):
        assert processor.clean_text("  hello  ") == "hello"

    def test_empty_string(self, processor):
        assert processor.clean_text("") == ""


class TestChunkText:
    def test_short_text_is_single_chunk(self, processor):
        chunks = processor.chunk_text("short text")
        assert len(chunks) == 1
        assert chunks[0] == "short text"

    def test_long_text_produces_multiple_chunks(self, processor):
        text = "token " * 300
        chunks = processor.chunk_text(text)
        assert len(chunks) > 1

    def test_chunk_size_respected(self, processor):
        text = "word " * 250
        chunks = processor.chunk_text(text)
        assert all(processor.count_tokens(c) <= processor.chunk_size for c in chunks)

    def test_overlap_creates_shared_content(self):
        proc = DocumentProcessor(chunk_size=20, overlap=5)
        text = "alpha beta gamma delta epsilon " * 40
        chunks = proc.chunk_text(text)
        assert len(chunks) >= 2
        first_tokens = proc._tokenizer.encode(chunks[0])
        second_tokens = proc._tokenizer.encode(chunks[1])
        assert first_tokens[-proc.overlap:] == second_tokens[:proc.overlap]

    def test_no_empty_chunks(self, processor):
        chunks = processor.chunk_text("hello world " * 20)
        assert all(len(c) > 0 for c in chunks)


class TestExtractMetadata:
    def test_txt_metadata_has_required_keys(self, processor):
        path = _write_temp_file("content", ".txt")
        try:
            meta = processor.extract_metadata(path)
            assert "title" in meta
            assert "author" in meta
            assert "date" in meta
            assert "file_type" in meta
        finally:
            os.unlink(path)

    def test_file_type_matches_extension(self, processor):
        path = _write_temp_file("content", ".txt")
        try:
            meta = processor.extract_metadata(path)
            assert meta["file_type"] == ".txt"
        finally:
            os.unlink(path)

    def test_date_is_set_when_missing(self, processor):
        path = _write_temp_file("content", ".txt")
        try:
            meta = processor.extract_metadata(path)
            assert meta["date"] is not None
        finally:
            os.unlink(path)


class TestMarkdownFrontmatter:
    def test_frontmatter_parses_title_and_tags(self, processor):
        content = """---
title: My Note
tags: [a, b]
section: concepts
---
Body line one.
"""
        path = _write_temp_file(content, ".md")
        try:
            result = processor.process_document(path, vault_root=None, relpath="wiki/note.md")
            assert result is not None
            assert result["metadata"]["title"] == "My Note"
            assert "a" in result["metadata"]["tags"]
            assert result["metadata"]["section"] == "concepts"
            assert "Body line one" in " ".join(result["chunks"])
        finally:
            os.unlink(path)

    def test_code_fences_omitted_from_chunks(self, processor):
        content = """Intro text.

```
skip this block
```

Outro text here.
"""
        path = _write_temp_file(content, ".md")
        try:
            result = processor.process_document(path, relpath="raw/x.md")
            assert result is not None
            joined = " ".join(result["chunks"]).lower()
            assert "skip this block" not in joined
            assert "intro" in joined
        finally:
            os.unlink(path)


class TestPdfExtraction:
    def test_extract_pdf_skips_failing_page(self, processor, monkeypatch):
        class _Page:
            def __init__(self, text: str | None = None, *, boom: bool = False):
                self._text = text
                self._boom = boom

            def extract_text(self) -> str:
                if self._boom:
                    raise UnboundLocalError("cannot access local variable 'cm'")
                return self._text or ""

        class _Reader:
            def __init__(self, _handle):
                self.pages = [_Page("hello "), _Page(boom=True), _Page("world")]

        monkeypatch.setattr("src.core.document_processor.PdfReader", _Reader)
        path = _write_temp_file("%PDF-1.4 stub", ".pdf")
        try:
            text = processor.extract_text(path)
            assert "hello" in text
            assert "world" in text
        finally:
            os.unlink(path)

    def test_extract_pdf_unreadable_raises(self, processor, monkeypatch):
        from pypdf.errors import PdfReadError

        def _boom(_handle):
            raise PdfReadError("bad pdf")

        monkeypatch.setattr("src.core.document_processor.PdfReader", _boom)
        path = _write_temp_file("%PDF-1.4 stub", ".pdf")
        try:
            with pytest.raises(ValueError, match="unreadable PDF"):
                processor.extract_text(path)
        finally:
            os.unlink(path)


class TestProcessDocument:
    def test_returns_dict_with_expected_keys(self, processor):
        path = _write_temp_file("Hello world content", ".txt")
        try:
            result = processor.process_document(path)
            assert result is not None
            assert "metadata" in result
            assert "chunks" in result
        finally:
            os.unlink(path)

    def test_duplicate_returns_none(self, processor):
        path = _write_temp_file("Identical content", ".txt")
        try:
            first = processor.process_document(path)
            second = processor.process_document(path)
            assert first is not None
            assert second is None
        finally:
            os.unlink(path)

    def test_different_files_not_flagged_as_duplicate(self, processor):
        path1 = _write_temp_file("Content A", ".txt")
        path2 = _write_temp_file("Content B", ".txt")
        try:
            assert processor.process_document(path1) is not None
            assert processor.process_document(path2) is not None
        finally:
            os.unlink(path1)
            os.unlink(path2)

    def test_identical_content_different_paths_both_ingest(self, processor):
        path1 = _write_temp_file("Same body", ".txt")
        path2 = _write_temp_file("Same body", ".txt")
        try:
            assert processor.process_document(path1) is not None
            assert processor.process_document(path2) is not None
        finally:
            os.unlink(path1)
            os.unlink(path2)
