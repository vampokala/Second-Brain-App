---
title: Doc Ingestion RAG Demo
emoji: 📚
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
license: mit
short_description: Citation-aware RAG with hybrid retrieval and truthfulness scoring
---

# Doc Ingestion — RAG Demo

A live demo of **Doc-Ingestion**, a citation-aware Retrieval-Augmented Generation system.

The Space runs **one container**: **FastAPI** on port **8000** serves both the **React** UI (static files) and the JSON/streaming API on the same origin.

## What you can do here

- Ask questions about **RAG**, **vector databases**, and **BM25 retrieval** — sample documents are pre-loaded.
- See **citations** pointing to the specific chunks that grounded each answer.
- See a **truthfulness score** (NLI faithfulness + citation groundedness) for every response.
- Choose between **OpenAI**, **Anthropic**, or **Gemini** providers using your own key (paste it in the UI).

## Limitations of this demo

- **No persistence across restarts** — state is ephemeral unless you attach HF storage / external backends.
- **Cloud LLM on this Space** — Hugging Face sets **`SPACE_ID`** in the container. The app uses that to **omit Ollama** from the provider list (there is no local Ollama daemon here). If you **clone the repo and run locally**, `SPACE_ID` is normally unset, so **Ollama stays available** per `config.yaml`. Details and overrides (`DOC_OLLAMA_ENABLED`) are in the main [README — Ollama and Hugging Face Spaces](../README.md#ollama-and-hugging-face-spaces).

## Dockerfile

Uses the repository root **`Dockerfile`**, which builds the React app and serves it from FastAPI.

If you change the Space listen port in Settings, ensure **`app_port`** in this README matches and that the container listens on **`PORT`** (defaults to **8000**).

## Run locally with full features

```bash
git clone https://github.com/vampokala/Doc-Ingestion
cd Doc-Ingestion
bash scripts/bootstrap_demo.sh
```

Or with Docker (API + UI on one port):

```bash
cp docker/.env.example docker/.env
# Edit docker/.env to add your API keys
docker compose -f docker/docker-compose.yml up --build
```

Open **http://localhost:8000** for the React UI and API.

## Source code

[github.com/vampokala/Doc-Ingestion](https://github.com/vampokala/Doc-Ingestion)
