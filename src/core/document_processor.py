'''
Multi-format support (PDF, DOCX, TXT, MD, HTML)
- Intelligent chunking with overlap
- Metadata extraction (title, author, date, file type)
- Text cleaning and normalization
- Duplicate detection
'''
import hashlib
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

import PyPDF2
import tiktoken
from bs4 import BeautifulSoup
from docx import Document


class _RegexTokenizer:
    """Offline fallback tokenizer when tiktoken encoding cannot be loaded."""

    _token_pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def encode(self, text: str) -> List[str]:
        return self._token_pattern.findall(text)

    def decode(self, token_ids: List[str]) -> str:
        if not token_ids:
            return ""
        return " ".join(token_ids)


class _Tokenizer(Protocol):
    def encode(self, text: str) -> List[Any]:
        ...

    def decode(self, token_ids: List[Any]) -> str:
        ...


class DocumentProcessor:
    def __init__(self, chunk_size: int = 600, overlap: int = 100, tokenizer_name: str = "gpt2"):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if overlap < 0:
            raise ValueError("overlap must be >= 0")
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.tokenizer_name = tokenizer_name
        self._tokenizer: _Tokenizer
        try:
            self._tokenizer = tiktoken.get_encoding(tokenizer_name)
        except Exception:
            self._tokenizer = _RegexTokenizer()
        self._seen_hashes: set = set()

    def process_document(self, file_path: str) -> Optional[Dict]:
        text = self.extract_text(file_path)
        if self._is_duplicate(text):
            return None
        metadata = self.extract_metadata(file_path)
        cleaned_text = self.clean_text(text)
        chunks = self.chunk_text(cleaned_text)
        return {
            'metadata': metadata,
            'chunks': chunks,
        }

    def _is_duplicate(self, text: str) -> bool:
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        if digest in self._seen_hashes:
            return True
        self._seen_hashes.add(digest)
        return False

    def extract_text(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        extractors = {
            '.pdf': self._extract_pdf_text,
            '.docx': self._extract_docx_text,
            '.txt': self._extract_plain_text,
            '.md': self._extract_plain_text,
            '.html': self._extract_html_text,
        }
        extractor = extractors.get(ext)
        if extractor is None:
            raise ValueError(f"Unsupported file type: {ext!r}")
        return extractor(file_path)

    def extract_metadata(self, file_path: str) -> Dict:
        ext = os.path.splitext(file_path)[1].lower()
        base = {
            'title': os.path.basename(file_path),
            'author': 'Unknown',
            'date': None,
            'file_type': ext,
        }
        if ext == '.pdf':
            base.update(self._pdf_metadata(file_path))
        elif ext == '.docx':
            base.update(self._docx_metadata(file_path))
        if base['date'] is None:
            base['date'] = datetime.now().isoformat()
        return base

    def clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def chunk_text(self, text: str) -> List[str]:
        token_ids = self._tokenizer.encode(text)
        if not token_ids:
            return []

        chunks: List[str] = []
        step = self.chunk_size - self.overlap
        start = 0
        while start < len(token_ids):
            end = min(start + self.chunk_size, len(token_ids))
            chunk = self._tokenizer.decode(token_ids[start:end])
            if chunk.strip():
                chunks.append(chunk)
            start += step
        return chunks

    def count_tokens(self, text: str) -> int:
        return len(self._tokenizer.encode(text))

    # --- private extractors ---

    def _extract_pdf_text(self, file_path: str) -> str:
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            return ''.join(page.extract_text() or '' for page in reader.pages)

    def _extract_docx_text(self, file_path: str) -> str:
        doc = Document(file_path)
        return '\n'.join(para.text for para in doc.paragraphs)

    def _extract_plain_text(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()

    def _extract_html_text(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        return soup.get_text(separator=' ')

    # --- private metadata helpers ---

    def _pdf_metadata(self, file_path: str) -> Dict:
        result = {}
        try:
            with open(file_path, 'rb') as f:
                info: Dict = dict(PyPDF2.PdfReader(f).metadata or {})
            if info.get('/Title'):
                result['title'] = info['/Title']
            if info.get('/Author'):
                result['author'] = info['/Author']
            if info.get('/CreationDate'):
                result['date'] = info['/CreationDate']
        except Exception:
            pass
        return result

    def _docx_metadata(self, file_path: str) -> Dict:
        result = {}
        try:
            props = Document(file_path).core_properties
            if props.title:
                result['title'] = props.title
            if props.author:
                result['author'] = props.author
            if props.created:
                result['date'] = props.created.isoformat()
        except Exception:
            pass
        return result
