"""
Phase 1 validation script.

Usage:
    python -m src.ingest --docs data/documents        # ingest a folder
    python -m src.ingest --docs path/to/file.pdf      # ingest a single file
    python -m src.ingest --docs data/documents --query "what is machine learning"
"""
import argparse
import os
import sys

from src.core.bm25_index import BM25Index
from src.core.document_processor import DocumentProcessor
from src.utils.config import load_config
from src.utils.database import VectorDatabase
from src.utils.log import get_logger, metrics, track_duration

logger = get_logger("ingest")

BM25_INDEX_PATH = "data/embeddings/bm25_index.json"
COLLECTION_NAME = "documents"


def collect_files(path: str) -> list[str]:
    supported = {".pdf", ".docx", ".txt", ".md", ".html"}
    if os.path.isfile(path):
        return [path] if os.path.splitext(path)[1].lower() in supported else []
    files = []
    for root, _, filenames in os.walk(path):
        for fname in filenames:
            if os.path.splitext(fname)[1].lower() in supported:
                files.append(os.path.join(root, fname))
    return sorted(files)


def ingest(
    docs_path: str,
    *,
    bm25_index_path: str = BM25_INDEX_PATH,
    collection_name: str = COLLECTION_NAME,
    chroma_path: str = "data/embeddings/chroma",
    processor: DocumentProcessor | None = None,
) -> tuple[BM25Index, VectorDatabase]:
    # ── 1. Config ────────────────────────────────────────────────────────────
    cfg = load_config("config.yaml")
    logger.info(
        "Config loaded: chunk_size=%d overlap=%d tokenizer=%s",
        cfg.chunk_size,
        cfg.overlap,
        cfg.chunk_tokenizer,
    )

    # ── 2. Components ─────────────────────────────────────────────────────────
    processor = processor or DocumentProcessor(
        chunk_size=cfg.chunk_size,
        overlap=cfg.overlap,
        tokenizer_name=cfg.chunk_tokenizer,
    )
    index = BM25Index()
    db = VectorDatabase(mode="dev", chroma_path=chroma_path)
    db.create_collection(collection_name)

    # ── 3. Process files ──────────────────────────────────────────────────────
    files = collect_files(docs_path)
    if not files:
        logger.info("No supported documents found in %s", docs_path)
        return index, db

    total_chunks = 0
    skipped = 0

    for file_path in files:
        logger.info("Processing: %s", file_path)
        with track_duration("document_processing", logger):
            result = processor.process_document(file_path)

        if result is None:
            logger.info("Skipped (duplicate): %s", file_path)
            skipped += 1
            continue

        chunks = result["chunks"]
        metadata = result["metadata"]

        # BM25 indexing (weighted title/metadata in index body; display text stays chunk-only)
        for i, chunk in enumerate(chunks):
            doc_id = f"{os.path.basename(file_path)}__chunk{i}"
            index_body = BM25Index.compose_index_text(chunk, metadata)
            index.add_document(doc_id, chunk, metadata, index_text=index_body)

        # Vector DB indexing
        vector_docs = [
            {"id": f"{os.path.basename(file_path)}__chunk{i}", "text": chunk, **metadata}
            for i, chunk in enumerate(chunks)
        ]
        with track_duration("vector_indexing", logger):
            db.add_documents(collection_name, vector_docs)

        total_chunks += len(chunks)
        logger.info("Indexed %d chunks from %s", len(chunks), os.path.basename(file_path))

    # ── 4. Persist BM25 index ─────────────────────────────────────────────────
    os.makedirs(os.path.dirname(bm25_index_path), exist_ok=True)
    index.save(bm25_index_path)

    # ── 5. Summary ────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Phase 1 Ingestion Summary")
    print("=" * 60)
    print(f"  Files processed  : {len(files) - skipped}")
    print(f"  Files skipped    : {skipped} (duplicates)")
    print(f"  Total chunks     : {total_chunks}")
    print(f"  BM25 index saved : {bm25_index_path}")
    print(f"  Vector DB        : {chroma_path}  (collection={collection_name!r})")

    perf = metrics.summary()
    if perf:
        print("\nPerformance:")
        for op, stats in perf.items():
            print(f"  {op}: mean={stats['mean']:.3f}s  max={stats['max']:.3f}s  count={int(stats['count'])}")
    print("=" * 60 + "\n")

    return index, db


def query(index: BM25Index, db: VectorDatabase, query_text: str, top_k: int = 3) -> None:
    print(f"\nQuery: {query_text!r}")

    print("\n── BM25 results ──────────────────────────────────────────")
    bm25_results = index.score(query_text, top_k=top_k)
    if bm25_results:
        for r in bm25_results:
            print(f"  [{r['score']:.4f}] {r['id']}")
            print(f"           {r['text'][:120].strip()}...")
    else:
        print("  No results.")

    print("\n── Vector DB results ─────────────────────────────────────")
    vector_results = db.query_documents(COLLECTION_NAME, query_text, top_k=top_k)
    if vector_results:
        for r in vector_results:
            print(f"  [dist={r['distance']:.4f}] {r['id']}")
            print(f"           {r['text'][:120].strip()}...")
    else:
        print("  No results.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents and validate Phase 1")
    parser.add_argument("--docs", required=True, help="Path to a file or folder to ingest")
    parser.add_argument("--query", default=None, help="Optional query to run after ingestion")
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to return")
    args = parser.parse_args()

    if not os.path.exists(args.docs):
        print(f"Error: path not found: {args.docs}", file=sys.stderr)
        sys.exit(1)

    index, db = ingest(args.docs)

    if args.query:
        query(index, db, args.query, top_k=args.top_k)


if __name__ == "__main__":
    main()
