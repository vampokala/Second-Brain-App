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

    def test_unsupported_format_raises(self, processor):
        path = _write_temp_file("data", ".csv")
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
