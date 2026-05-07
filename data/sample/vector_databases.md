# Vector Databases

A vector database is a data management system designed specifically to store, index, and query high-dimensional vectors. These vectors are typically dense numerical representations (embeddings) of text, images, audio, or other data produced by machine learning models. Vector databases are a foundational component in modern AI-powered search and retrieval systems.

## What is an Embedding?

An embedding is a fixed-length numerical array that encodes the semantic meaning of a piece of content. Two pieces of content that are semantically similar will have embeddings with a high cosine similarity. Embedding models such as `nomic-embed-text`, `text-embedding-ada-002`, and `all-MiniLM-L6-v2` produce these representations.

Typical embedding dimensions range from 384 to 3072, depending on the model. Storing and searching millions of such vectors efficiently requires purpose-built indexing structures.

## Core Operations

A vector database supports four primary operations:

- **Upsert:** Insert or update a vector along with its metadata (document ID, source file, chunk text, etc.).
- **Nearest neighbour search (ANN):** Given a query vector, return the K most similar vectors according to a distance metric such as cosine similarity or Euclidean distance.
- **Delete:** Remove a vector by ID.
- **Filter:** Combine a vector search with metadata filters (e.g., return only chunks from a given document or date range).

## Indexing Algorithms

Exact nearest neighbour search is O(n) per query and becomes impractical at scale. Approximate Nearest Neighbour (ANN) algorithms trade a small amount of accuracy for orders-of-magnitude speed:

- **HNSW (Hierarchical Navigable Small World):** A graph-based index with excellent recall and low latency. Used by Qdrant, Weaviate, and many others.
- **IVF (Inverted File Index):** Clusters vectors into cells; at query time only nearby cells are searched. Used in FAISS and Chroma.
- **Flat index:** Exact brute-force search. Useful only for small datasets or where perfect recall is required.

## Popular Vector Databases

- **Chroma:** Lightweight, embeddable, designed for local development and small to mid-scale use cases. No server required — runs in-process.
- **Qdrant:** Production-grade, Rust-based, supports HNSW with payload filtering. Available as a self-hosted server or cloud service.
- **Weaviate:** Open-source, multi-modal, built-in support for hybrid search (BM25 + vector).
- **Pinecone:** Fully managed cloud service with serverless and pod-based tiers.
- **FAISS:** Facebook AI's library for fast similarity search. Not a full database (no CRUD), but highly optimised for bulk operations.

## Hybrid Search in Vector Databases

Many modern vector databases support hybrid search — combining dense vector search with sparse keyword (BM25) search in a single query. The scores from both methods are fused to produce a final ranked list. Qdrant and Weaviate both support this natively. When hybrid search is not built in, it can be implemented at the application layer by running two separate queries and fusing the results.

## Relevance to RAG

In a RAG pipeline, the vector database serves as the retrieval backend. Ingested document chunks are stored as vectors; at query time the user's question is embedded and the K nearest chunks are retrieved. The choice of database affects latency, scalability, and the ability to filter results by metadata (e.g., restricting retrieval to chunks from a particular document or collection).
