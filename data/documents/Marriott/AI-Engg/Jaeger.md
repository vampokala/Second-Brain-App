Jaeger is a tool for distributed tracing.

In your TIPAI architecture, a single user request (like "tell me about pet policy") triggers a complex chain of events across multiple services:

API → Temporal Workflow → Orchestrator → Worker → LLM (Azure/OpenAI) → Redis

Jaeger visualizes this entire flow as a timeline (waterfall view), allowing you to see:

1. Latency: Exactly how long each step took (e.g., "Why did this response take 5 seconds? Was it the LLM or the database?").

2. Errors: If a request failed, Jaeger shows you exactly where in the chain it broke.

3. Dependencies: How your services interact with each other.

It is extremely useful for debugging performance issues and understanding what your AI agents are actually doing behind the scenes.