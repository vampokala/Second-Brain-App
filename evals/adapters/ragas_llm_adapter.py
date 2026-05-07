"""LangChain BaseChatModel adapter wrapping LLMProviderRouter.

Enables RAGAS (which requires a LangChain LLM) to use whichever provider
the user has configured (Ollama, OpenAI, Anthropic, Gemini).

Usage:
    from evals.adapters.ragas_llm_adapter import make_ragas_llm
    llm = make_ragas_llm(router, provider="ollama", model="qwen2.5:7b")
"""

from __future__ import annotations

from typing import Any, Iterator, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel  # type: ignore[import-untyped]
from langchain_core.messages import AIMessage, BaseMessage  # type: ignore[import-untyped]
from langchain_core.outputs import ChatGeneration, ChatResult  # type: ignore[import-untyped]
from ragas.llms import LangchainLLMWrapper  # type: ignore[import-untyped]

from src.core.llm_provider import LLMProviderRouter


class _RouterChatModel(BaseChatModel):
    """Thin wrapper around LLMProviderRouter as a LangChain ChatModel."""

    router: Any
    provider: str
    model_id: str

    class Config:
        arbitrary_types_allowed = True

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt = "\n".join(
            getattr(m, "content", "") for m in messages if getattr(m, "content", None)
        )
        text = self.router.generate(self.provider, self.model_id, prompt)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    @property
    def _llm_type(self) -> str:
        return f"doc-ingestion-{self.provider}"


def make_ragas_llm(
    router: LLMProviderRouter,
    provider: str,
    model: str,
) -> LangchainLLMWrapper:
    """Return a RAGAS-compatible LLM wrapper backed by LLMProviderRouter."""
    chat_model = _RouterChatModel(router=router, provider=provider, model_id=model)
    return LangchainLLMWrapper(chat_model)
