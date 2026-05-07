# Retrieval-Augmented Generation (RAG)

Retrieval-Augmented Generation (RAG) is a technique that enhances large language model (LLM) responses by dynamically retrieving relevant information from an external knowledge base before generating an answer. This approach grounds the model's output in specific documents rather than relying solely on knowledge encoded during training.

## How RAG Works

A RAG system has two main phases:

**Ingestion phase:** Documents are split into smaller chunks, converted into vector embeddings using an embedding model, and stored in a vector database. Many systems also build a sparse index (such as BM25) over the same chunks for keyword-based retrieval.

**Query phase:** When a user asks a question, the system retrieves the most relevant chunks from the vector store (semantic search) and the sparse index (keyword search). These retrieved chunks are then inserted into the LLM's context window along with the question, and the model generates an answer grounded in those documents.

## Why RAG?

RAG solves several limitations of plain LLMs:

- **Factual accuracy:** The model answers from retrieved documents rather than potentially hallucinating facts it did not learn during training.
- **Up-to-date knowledge:** External documents can be updated or replaced without retraining the model.
- **Source attribution:** Answers can cite the specific chunks they are drawn from, making them auditable.
- **Domain specialization:** A RAG system can be pointed at proprietary or domain-specific document collections that the base model has never seen.

## Retrieval Strategies

Several retrieval strategies exist:

- **Dense retrieval:** Uses embedding similarity (cosine or dot product) to find semantically related chunks. Effective for paraphrased or synonym-heavy queries.
- **Sparse retrieval (BM25):** Uses term frequency and inverse document frequency scoring. Effective for exact keyword matches and technical terms.
- **Hybrid retrieval:** Combines dense and sparse scores using a fusion algorithm such as Reciprocal Rank Fusion (RRF). Consistently outperforms either method alone across diverse query types.
- **Re-ranking:** A second-stage cross-encoder model scores (query, chunk) pairs more precisely than first-stage retrieval. Improves precision at the cost of extra compute.

## Context Window and Prompting

After retrieval, the system inserts the top-ranked chunks into the LLM prompt. A context optimizer typically counts tokens to stay within the model's context limit. The prompt structure usually includes an instruction, the retrieved context, and the user question.

## Evaluation

RAG quality is typically measured along two axes:

1. **Retrieval quality:** Precision@K, Recall@K, MRR, and NDCG measure whether the right chunks are retrieved.
2. **Generation quality:** Faithfulness (does the answer stay within the source material?), answer relevance, and correctness (against a gold answer) measure generation quality.

The most damaging failure mode is hallucination — the model stating something not supported by the retrieved context. Citation tracking and faithfulness scoring help detect and reduce this problem.
