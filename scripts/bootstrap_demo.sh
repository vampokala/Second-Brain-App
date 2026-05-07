#!/usr/bin/env bash
# Bootstrap a local demo: creates venv, installs deps, optionally pulls Ollama models,
# then ingests the sample documents so you can query immediately.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "==> Checking Python 3.10+"
python3 --version

echo "==> Creating virtual environment (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
pip install --upgrade pip -q
pip install -r requirements/base.txt -q

echo "==> Setting up HuggingFace cache directories"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TRANSFORMERS_CACHE="$HF_HOME/transformers"
export SENTENCE_TRANSFORMERS_HOME="$HF_HOME/sentence_transformers"

if command -v ollama &>/dev/null; then
  echo "==> Pulling Ollama embedding model (nomic-embed-text)"
  ollama pull nomic-embed-text || echo "  [warn] could not pull nomic-embed-text — check Ollama is running"
  echo "==> Pulling Ollama chat model (qwen2.5:7b)"
  ollama pull qwen2.5:7b || echo "  [warn] could not pull qwen2.5:7b — check Ollama is running"
else
  echo "  [info] Ollama not found. Skipping model pull."
  echo "  [info] To use local models, install Ollama from https://ollama.ai and re-run."
  echo "  [info] You can still use cloud providers (OpenAI/Anthropic/Gemini) by setting API keys."
fi

echo "==> Ingesting sample documents from data/sample/"
PYTHONPATH="$REPO_ROOT" python3 -m src.ingest --docs data/sample

echo ""
echo "Bootstrap complete. Start the app:"
echo ""
echo "  # API server"
echo "  PYTHONPATH=. .venv/bin/uvicorn src.api.main:app --reload --port 8000"
echo ""
echo "  # Streamlit UI (in a second terminal)"
echo "  PYTHONPATH=. .venv/bin/streamlit run src/web/streamlit_app.py"
echo ""
echo "  # Or try a CLI query:"
echo "  PYTHONPATH=. .venv/bin/python -m src.query 'What is RAG?'"
