"""Streamlit UI for querying and ingesting documents."""

from __future__ import annotations

import os

import requests
import streamlit as st
from src.core.rag_orchestrator import QueryRequest, QueryResponse, RAGOrchestrator
from src.utils.config import load_config, provider_api_key_env
from src.web.ingestion_service import run_ingest, save_uploaded_files

API_BASE_URL = os.getenv("DOC_INGEST_API_URL", "http://127.0.0.1:8000")
UPLOAD_DIR = os.getenv("DOC_UPLOAD_DIR", "data/documents/uploads")
# DOC_API_KEY takes precedence; fall back to first key in DOC_API_KEYS (set by spaces/app.py).
API_KEY = os.getenv("DOC_API_KEY") or (os.getenv("DOC_API_KEYS", "").split(",")[0].strip())
DEFAULT_UI_GATEWAY_KEY = os.getenv("DOC_API_KEY_DEFAULT", "ev-key-1")

# When DOC_PROFILE=demo the UI disables uploads and shows a banner.
_DEMO_MODE = os.getenv("DOC_PROFILE", "").strip().lower() == "demo"
_DEMO_UPLOADS_ENABLED = os.getenv("DOC_DEMO_UPLOADS", "0").strip() == "1"

_DEMO_QUESTIONS = [
    "What is Retrieval-Augmented Generation?",
    "What are the two main phases of a RAG system?",
    "How does hybrid retrieval work?",
    "What is BM25 and how does it differ from vector search?",
    "What are the weaknesses of BM25?",
    "What is Reciprocal Rank Fusion (RRF)?",
    "What is a vector database?",
    "What is HNSW?",
    "What is the difference between Chroma and Qdrant?",
    "Why use hybrid retrieval instead of just dense vector search?",
    "What failure mode does citation tracking help detect?",
    "How are embeddings used in a RAG pipeline?",
]


@st.cache_resource(show_spinner=False)
def _get_demo_orchestrator() -> RAGOrchestrator:
    """Build one orchestrator per Streamlit process for demo in-process querying."""
    return RAGOrchestrator(load_config("config.yaml"))


def _normalize_orchestrator_response(out: QueryResponse) -> dict:
    retrieved = []
    for item in out.retrieved:
        legacy = item.to_legacy_dict()
        retrieved.append(
            {
                "id": legacy["id"],
                "score": float(legacy.get("score") or 0.0),
                "source": str(legacy.get("source") or "hybrid"),
                "confidence": float(legacy.get("confidence") or 0.0),
                "metadata": dict(legacy.get("metadata") or {}),
                "preview": (legacy.get("text") or "")[:240],
            }
        )

    truthfulness = None
    if out.truthfulness is not None:
        truthfulness = {
            "nli_faithfulness": out.truthfulness.nli_faithfulness,
            "citation_groundedness": out.truthfulness.citation_groundedness,
            "uncited_claims": out.truthfulness.uncited_claims,
            "score": out.truthfulness.score,
        }

    return {
        "query": out.query,
        "provider": out.provider,
        "model": out.model,
        "answer": out.answer,
        "processing_time_ms": out.processing_time_ms,
        "cached": out.cached,
        "validation_issues": out.validation_issues,
        "citations": out.citations,
        "retrieved": retrieved,
        "truthfulness": truthfulness,
    }


def _run_query_in_demo_mode(payload: dict) -> dict:
    """Run query through shared orchestrator instead of localhost HTTP API."""
    orchestrator = _get_demo_orchestrator()
    req = QueryRequest(
        query_text=str(payload.get("query", "")),
        top_k=int(payload.get("top_k", 5)),
        use_llm=bool(payload.get("use_llm", True)),
        use_rerank=bool(payload.get("use_rerank", True)),
        stream=bool(payload.get("stream", False)),
        provider=str(payload.get("provider") or "") or None,
        model=str(payload.get("model") or "") or None,
        provider_api_key=str(payload.get("provider_api_key") or "") or None,
        include_citations=bool(payload.get("include_citations", True)),
    )
    out = orchestrator.run(req)
    return _normalize_orchestrator_response(out)


def _run_query_via_api(payload: dict, headers: dict) -> dict:
    resp = requests.post(f"{API_BASE_URL}/query", json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _get_or_create_demo_session(headers: dict) -> str:
    existing = str(st.session_state.get("demo_session_id", "")).strip()
    if existing:
        try:
            probe = requests.get(f"{API_BASE_URL}/sessions/{existing}", headers=headers, timeout=15)
            if probe.ok:
                return existing
        except Exception:
            pass
    resp = requests.post(f"{API_BASE_URL}/sessions", headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    sid = str(data.get("session_id", "")).strip()
    if sid:
        st.session_state["demo_session_id"] = sid
    return sid


def _truthfulness_badge(score: float) -> str:
    """Return a coloured emoji label for a truthfulness score in [0, 1]."""
    if score >= 0.8:
        return f"🟢 Truthfulness: {score:.2f}"
    if score >= 0.5:
        return f"🟡 Truthfulness: {score:.2f}"
    return f"🔴 Truthfulness: {score:.2f}"


def _provider_ready(provider: str, session_provider_key: str = "") -> bool:
    if _DEMO_MODE:
        # Hosted demo uses server-side provider secrets.
        return True
    if session_provider_key.strip():
        return True
    env_name = provider_api_key_env(provider)
    if env_name is None:
        return True
    return bool(os.getenv(env_name))


def _api_key_from_session_or_env(default_key: str) -> str:
    session_key = str(st.session_state.get("doc_api_key", "")).strip()
    if session_key:
        return session_key
    env_key = API_KEY.strip()
    if env_key:
        return env_key
    return default_key


def _gateway_default_from_config(cfg) -> str:
    env_key = API_KEY.strip()
    if env_key:
        return env_key
    api_cfg = getattr(cfg, "api", None)
    if api_cfg and getattr(api_cfg, "api_keys", None):
        keys = [k for k in api_cfg.api_keys if str(k).strip()]
        if keys:
            return str(keys[0]).strip()
    return DEFAULT_UI_GATEWAY_KEY


def _render_auth_controls(auth_required: bool, default_key: str) -> str:
    # Auto-seed session key from env/default so the field is pre-populated.
    if not str(st.session_state.get("doc_api_key", "")).strip():
        st.session_state["doc_api_key"] = default_key

    with st.sidebar.expander("Session Security", expanded=False):
        st.caption("Session-only key for API auth. Not written to disk.")
        current = str(st.session_state.get("doc_api_key", ""))
        entered = st.text_input(
            "API Gateway Key (X-API-Key)",
            value=current,
            type="password",
            help="Used for API auth when enabled. Stored in this Streamlit session only.",
        )
        if entered != current:
            st.session_state["doc_api_key"] = entered.strip()
        if st.button("Clear session key"):
            st.session_state["doc_api_key"] = ""
            st.success("Session key cleared.")
    resolved = _api_key_from_session_or_env(default_key)
    if auth_required and resolved:
        st.sidebar.success("API key available for authenticated requests.")
    elif auth_required:
        st.sidebar.warning("No API key available for authenticated cloud requests.")
    return resolved


def _provider_key_from_session(provider: str) -> str:
    key_map = {
        "openai": "provider_key_openai",
        "anthropic": "provider_key_anthropic",
        "gemini": "provider_key_gemini",
    }
    slot = key_map.get(provider, "")
    if not slot:
        return ""
    return str(st.session_state.get(slot, "")).strip()


def _render_query_tab() -> None:
    cfg = load_config("config.yaml")
    st.subheader("Ask a question")

    if _DEMO_MODE:
        st.markdown("**Try one of these sample questions** (click to fill):")
        cols = st.columns(2)
        for idx, q in enumerate(_DEMO_QUESTIONS):
            if cols[idx % 2].button(q, key=f"demo_q_{idx}", use_container_width=True):
                st.session_state["demo_prompt"] = q
        st.markdown("---")
    providers = list(cfg.llm.allowed_models_by_provider.keys())
    default_provider = cfg.llm.default_provider if cfg.llm.default_provider in providers else providers[0]
    selected_provider = st.selectbox("Provider", options=providers, index=providers.index(default_provider))
    model_options = cfg.llm.allowed_models_by_provider.get(selected_provider, [])
    default_model = cfg.llm.default_model_by_provider.get(selected_provider)
    idx = model_options.index(default_model) if default_model in model_options else 0
    selected_model = st.selectbox("Model", options=model_options, index=idx)
    remember = st.checkbox("Remember last selection", value=True)
    stream = st.checkbox("Stream response", value=False, help="Currently treated as standard response in API.")
    default_prompt = str(st.session_state.pop("demo_prompt", ""))
    prompt = st.text_area(
        "Prompt",
        value=default_prompt,
        height=160,
        placeholder="Ask something about your ingested documents...",
    )
    auth_required = bool(getattr(cfg, "api", None) and cfg.api.auth_enabled)
    default_gateway_key = _gateway_default_from_config(cfg)
    if _DEMO_MODE:
        resolved_api_key = _api_key_from_session_or_env(default_gateway_key)
    else:
        resolved_api_key = _render_auth_controls(auth_required, default_gateway_key)
    require_api_key_for_provider = auth_required and (not _DEMO_MODE) and selected_provider != "ollama"

    if _DEMO_MODE:
        st.sidebar.caption("Demo mode uses server-side provider secrets.")
    else:
        with st.sidebar.expander("Provider Keys (session-only)", expanded=False):
            st.caption("Optional: paste provider API keys for this browser session.")
            with st.form("provider_keys_form", clear_on_submit=False):
                openai_input = st.text_input(
                    "OpenAI key",
                    value=str(st.session_state.get("provider_key_openai", "")),
                    type="password",
                )
                anthropic_input = st.text_input(
                    "Anthropic key",
                    value=str(st.session_state.get("provider_key_anthropic", "")),
                    type="password",
                )
                gemini_input = st.text_input(
                    "Gemini key",
                    value=str(st.session_state.get("provider_key_gemini", "")),
                    type="password",
                )
                applied = st.form_submit_button("Apply provider keys")
                if applied:
                    st.session_state["provider_key_openai"] = openai_input.strip()
                    st.session_state["provider_key_anthropic"] = anthropic_input.strip()
                    st.session_state["provider_key_gemini"] = gemini_input.strip()
                    st.success("Provider session keys applied.")
            if st.button("Clear provider keys"):
                st.session_state["provider_key_openai"] = ""
                st.session_state["provider_key_anthropic"] = ""
                st.session_state["provider_key_gemini"] = ""
                st.success("Provider session keys cleared.")

    if require_api_key_for_provider and not resolved_api_key:
        st.warning(
            "API authentication is enabled for non-local providers but DOC_API_KEY is not set. "
            "Set DOC_API_KEY or use the session key input in the sidebar."
        )

    selected_provider_session_key = _provider_key_from_session(selected_provider)

    if not _provider_ready(selected_provider, selected_provider_session_key):
        env_name = provider_api_key_env(selected_provider)
        st.warning(
            f"{env_name} is not set in environment. "
            f"Paste a session key in sidebar to use {selected_provider}."
        )

    run_disabled = (not prompt.strip()) or (require_api_key_for_provider and not resolved_api_key)
    if st.button("Run", type="primary", disabled=run_disabled):
        provider_session_key = _provider_key_from_session(selected_provider)
        if not _provider_ready(selected_provider, provider_session_key):
            st.error("Selected provider is unavailable due to missing API key.")
            return

        payload = {
            "query": prompt.strip(),
            "provider": selected_provider,
            "model": selected_model,
            "stream": stream,
            "include_citations": True,
            "top_k": 5,
        }
        if provider_session_key:
            payload["provider_api_key"] = provider_session_key
        headers = {"Content-Type": "application/json"}
        if resolved_api_key:
            headers["X-API-Key"] = resolved_api_key
        with st.spinner("Running retrieval and generation..."):
            try:
                if _DEMO_MODE and not _DEMO_UPLOADS_ENABLED:
                    data = _run_query_in_demo_mode(payload)
                else:
                    if _DEMO_MODE and _DEMO_UPLOADS_ENABLED:
                        sid = _get_or_create_demo_session(headers)
                        payload["session_id"] = sid
                    data = _run_query_via_api(payload, headers)
            except requests.HTTPError as exc:
                msg = "Request failed."
                try:
                    err = exc.response.json() if exc.response is not None else {}
                    detail = err.get("detail")
                    if detail:
                        msg = f"Request failed: {detail}"
                except Exception:
                    if exc.response is not None:
                        msg = f"Request failed: {exc.response.status_code} {exc.response.reason}"
                st.error(msg)
                return
            except Exception as exc:
                st.error(f"Request failed: {exc}")
                return

        st.markdown("### Answer")
        st.write(data.get("answer", ""))

        truthfulness = data.get("truthfulness")
        if truthfulness:
            badge = _truthfulness_badge(float(truthfulness.get("score", 0.0)))
            st.caption(
                f"{badge} | NLI faithfulness: {truthfulness.get('nli_faithfulness', 0.0):.2f} | "
                f"Citation groundedness: {truthfulness.get('citation_groundedness', 0.0):.2f} | "
                f"Uncited claims: {truthfulness.get('uncited_claims', 0)}"
            )

        st.caption(
            f"Provider: {data.get('provider')} | Model: {data.get('model')} | "
            f"Latency: {data.get('processing_time_ms', 0):.0f} ms"
        )

        citations = data.get("citations", [])
        if citations:
            st.markdown("### Citations")
            for c in citations:
                st.write(
                    f"- `{c.get('chunk_id')}` | resolved={c.get('resolved')} | "
                    f"score={float(c.get('verification_score', 0.0)):.2f}"
                )

        retrieved = data.get("retrieved", [])
        if retrieved:
            st.markdown("### Retrieved Chunks")
            for r in retrieved:
                st.write(f"- `{r.get('id')}` ({r.get('source')}, score={float(r.get('score', 0.0)):.3f})")
                st.caption(r.get("preview", ""))

        if remember:
            st.session_state["provider"] = selected_provider
            st.session_state["model"] = selected_model


def _render_ingest_tab() -> None:
    st.subheader("Ingest new documents")
    if _DEMO_MODE and not _DEMO_UPLOADS_ENABLED:
        st.info(
            "**Hosted demo** — uploads are disabled to prevent abuse. "
            "Sample documents (RAG, vector databases, BM25) are pre-loaded and ready to query. "
            "Clone the repo and run locally to ingest your own documents."
        )
        return
    st.markdown(
        """
1. Upload supported files (`.pdf`, `.docx`, `.txt`, `.md`, `.html`).
2. Click **Ingest** to chunk, embed, and store in vector and BM25 indexes.
3. Query tab will use newly ingested files after processing completes.
"""
    )
    uploads = st.file_uploader(
        "Upload files",
        type=["pdf", "docx", "txt", "md", "html"],
        accept_multiple_files=True,
    )
    if st.button("Ingest"):
        if not uploads:
            st.warning("Select one or more files before ingesting.")
            return
        cfg = load_config("config.yaml")
        auth_required = bool(getattr(cfg, "api", None) and cfg.api.auth_enabled)
        default_gateway_key = _gateway_default_from_config(cfg)
        resolved_api_key = _api_key_from_session_or_env(default_gateway_key)
        headers = {}
        if auth_required and resolved_api_key:
            headers["X-API-Key"] = resolved_api_key

        if _DEMO_MODE and _DEMO_UPLOADS_ENABLED:
            sid = _get_or_create_demo_session(headers)
            files_payload = [
                ("files", (u.name, u.getvalue(), "application/octet-stream"))
                for u in uploads
            ]
            with st.spinner("Uploading and indexing session documents..."):
                resp = requests.post(
                    f"{API_BASE_URL}/sessions/{sid}/documents",
                    files=files_payload,
                    headers=headers,
                    timeout=180,
                )
            if not resp.ok:
                st.error(f"Upload failed: {resp.status_code} {resp.text}")
                return
            data = resp.json()
            for item in data.get("results", []):
                st.write(f"- {item.get('filename')}: {item.get('status')} ({item.get('message')})")
            queued = [r for r in data.get("results", []) if r.get("status") == "queued"]
            summary = {"processed_files": len(queued), "status": "ok"}
        else:
            staged = save_uploaded_files(UPLOAD_DIR, uploads)
            for item in staged:
                st.write(f"- {item.filename}: {item.status} ({item.message})")
            with st.spinner("Running ingestion pipeline..."):
                summary = run_ingest(UPLOAD_DIR)
        st.success(f"Ingestion complete: {summary}")


def main() -> None:
    st.set_page_config(page_title="Doc Ingestion UI", layout="wide")
    st.title("Doc Ingestion Assistant")
    if _DEMO_MODE:
        st.info(
            "**Hosted demo** — querying sample documents (RAG, vector databases, BM25) "
            "via a cloud LLM. No data is persisted between sessions. "
            "[Run locally](https://github.com/vampokala/Doc-Ingestion#quickstart) for full functionality."
        )
    query_tab, ingest_tab = st.tabs(["Query", "Ingest"])
    with query_tab:
        _render_query_tab()
    with ingest_tab:
        _render_ingest_tab()


if __name__ == "__main__":
    main()
