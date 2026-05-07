# Project Overview

Doc-Ingestion is a citation-aware RAG system with three user-facing surfaces:

- CLI (`src/query.py`, `src/ingest.py`)
- FastAPI (`src/api/main.py`)
- Streamlit (`src/web/streamlit_app.py`)

## System map

```mermaid
flowchart LR
  client[User] --> cli[CLI]
  client --> api[FastAPI]
  client --> ui[Streamlit]
  cli --> orchestrator[RAGOrchestrator]
  api --> orchestrator
  ui --> orchestrator
  orchestrator --> hybrid[HybridRetriever]
  hybrid --> rerank[CrossEncoderReranker]
  rerank --> gen[RAGGenerator]
  gen --> cite[CitationTrackerAndVerifier]
  gen --> providers[LLMProviderRouter]
  providers --> ollama[Ollama]
  providers --> openai[OpenAI]
  providers --> claude[AnthropicClaude]
  providers --> gemini[Gemini]
  orchestrator --> bm25[BM25Index]
  orchestrator --> vector[VectorStore]
```

## Retrieval and citation lifecycle

1. Query is normalized and sent to BM25 + vector retrieval.
2. Ranked IDs are fused with weighted RRF.
3. Optional cross-encoder reranking narrows final context.
4. Prompt is generated and sent to selected provider/model.
5. Citations are extracted, mapped to chunk IDs, and verification-scored.
6. Structured response is returned to CLI/API/UI.

## Ingestion lifecycle

1. Files are parsed and chunked by `DocumentProcessor`.
2. Chunks are inserted into BM25 index.
3. Embeddings are generated and upserted to vector DB.
4. Streamlit ingest tab can stage uploads and trigger this flow.
# Project Overview

Purpose: summarize what this project does, why it is useful, and how it is designed.  
Audience: first-time visitors, interviewers, and engineers doing a quick architecture review.  
Reading time: 4-6 minutes.

## What this project is

Doc-Ingestion is a local-first RAG system that converts document collections into grounded Q&A answers. Instead of querying a closed dataset or relying on a generic chatbot response, it retrieves evidence from user-provided files and builds answers from those sources.

## Problem statement

Teams often store information across PDFs, markdown notes, and text files. Finding reliable answers is slow and error-prone when search is weak and responses are not grounded. This project addresses that by combining lexical and semantic retrieval with a generation layer designed to stay tied to retrieved context.

## Solution summary

- Ingest and normalize multiple document formats.
- Build both sparse and dense indexes.
- Combine retrieval results using reciprocal rank fusion.
- Improve ranking quality with cross-encoder reranking.
- Optimize context and generate responses through Ollama.
- Evaluate retrieval and generation quality with explicit metrics modules.

## Architecture at a glance

```mermaid
flowchart LR
  subgraph inputs [Inputs]
    docs[DocumentFiles]
    question[UserQuestion]
  end
  subgraph ingestPath [IngestionPath]
    process[DocumentProcessAndChunk]
    bm25[BM25Index]
    vector[VectorStore]
  end
  subgraph queryPath [QueryPath]
    retrieve[HybridRetrieve]
    rerank[CrossEncoderRerank]
    context[ContextOptimize]
    gen[RAGGenerate]
  end
  docs --> process
  process --> bm25
  process --> vector
  question --> retrieve
  bm25 --> retrieve
  vector --> retrieve
  retrieve --> rerank
  rerank --> context
  context --> gen
```

## Query lifecycle

```mermaid
flowchart TD
  startQ[StartQuery] --> parseQ[QueryProcess]
  parseQ --> hybridQ[HybridRetrieve]
  hybridQ --> fuseQ[RrfFuse]
  fuseQ --> rerankQ[CrossEncoderRerank]
  rerankQ --> optimizeQ[ContextOptimize]
  optimizeQ --> promptQ[PromptBuild]
  promptQ --> answerQ[GenerateAnswer]
  answerQ --> validateQ[ValidateAndFormat]
  validateQ --> endQ[FinalOutput]
```

## Why this is a strong portfolio project

- Demonstrates full-stack AI system design, not just prompt calls.
- Shows quality focus through retrieval and generation evaluation modules.
- Uses practical local inference workflows (Ollama) and production-minded retrieval abstractions.
- Includes modular code boundaries that support iteration and extension.

## Where to go deeper

- Root documentation: [`../README.md`](../README.md)
- Docs hub: [`README.md`](README.md)
- Hybrid retrieval internals: [`phase2_hybrid_retrieval.md`](phase2_hybrid_retrieval.md)
- Reranking and generation plan: [`phase3_reranking_generation.md`](phase3_reranking_generation.md)
- Public progress: [`ROADMAP.md`](ROADMAP.md)
