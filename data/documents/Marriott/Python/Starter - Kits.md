
Suggested refactoring for python starter kit
```
src/
  ai_app/
    domain/
      models/          # Message, ToolCall, ConversationState, etc.
      services/        # AgentOrchestrator, Router, RAGCoordinator
      ports/           # LLMClientPort, EmbeddingPort, ToolPort, StorePort
    application/
      use_cases/       # AnswerQuestion, SummarizeDoc, RunWorkflow
      dto/             # Request/response DTOs (if you want them)
    infrastructure/
      llm/
        litellm_client.py      # LiteLLM adapter
        openai_client.py       # optional alt adapter
      tools/
        http_tool_adapter.py   # wraps external tools/APIs
      storage/
        pg_vector_store.py
        redis_state_store.py
      entrypoints/
        fastapi_http.py        # REST API adapter
        cli.py                 # CLI adapter
```




