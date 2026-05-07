I'll review both projects to compile the tech stack and frameworks used. Let me explore the key configuration files and documentation.

[4 tools called]

Let me also explore the frontend and look at a few more files to complete the tech stack analysis.

[4 tools called]

Let me look at a few more files to complete my understanding of the observability and infrastructure stack.

[2 tools called]

Now I have a comprehensive view of the tech stack. Let me compile the job requirements for a Mid-level AI Engineer position based on both projects.

---

## 📋 Tech Stack Summary & Job Requirements

### **Complete Technology Stack Used in TIP.AI V3 Platform**

Based on my review of both `mi-tipv3-alpha` (Central Platform) and `mi-tipv3-worker-alpha` (Worker Template) projects, here is the complete tech stack:

---

### **🤖 AI/ML Frameworks & LLM Integration**

| Technology                 | Purpose                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| **LiteLLM**                | Multi-provider LLM abstraction (OpenAI, Azure OpenAI, etc.)          |
| **OpenAI GPT-4/GPT-4o**    | LLM for planning, query decomposition, slot filling, ReAct reasoning |
| **Azure OpenAI**           | Enterprise LLM deployment                                            |
| **text-embedding-3-small** | Vector embeddings for semantic intent search                         |
| **scikit-learn**           | ML utilities                                                         |
| **ReAct Pattern**          | Reasoning + Action pattern for agentic tool execution                |

---

### **🐍 Backend Frameworks & Languages**

| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.10+ | Primary programming language |
| **FastAPI** | 0.115+ | REST API framework with OpenAPI 3.1 |
| **Pydantic** | 2.0+ | Data validation, type-safe settings |
| **Temporal** | 1.20+ | Durable workflow orchestration engine |
| **Temporal Nexus** | - | Cross-namespace service communication |
| **asyncio** | - | Async programming patterns |

---

### **💾 Databases & Storage**

| Technology | Version | Purpose |
|------------|---------|---------|
| **PostgreSQL** | 15+ | Temporal persistence & Intent Registry |
| **pgvector** | - | Vector similarity search extension |
| **Neo4j** | 5.21+ | Knowledge graph (property/hotel data) |
| **Redis** | 7+ | Event streaming (SSE), caching |
| **AWS S3** | - | Large payload blob storage |

---

### **🖥️ Frontend Technologies**

| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 19.0 | UI framework |
| **Vite** | 6.0 | Build tool & dev server |
| **Tailwind CSS** | 3.4 | Utility-first CSS framework |
| **PostCSS/Autoprefixer** | - | CSS processing |

---

### **🔧 Infrastructure & DevOps**

| Technology | Purpose |
|------------|---------|
| **Docker & Docker Compose** | Containerization & orchestration |
| **OpenTelemetry (OTel)** | Distributed tracing |
| **OTLP Collector** | Trace aggregation & forwarding |
| **Jaeger** | Tracing UI (development) |
| **Dynatrace** | Production observability |

---

### **📡 Protocols & Communication**

| Technology | Purpose |
|------------|---------|
| **REST API** | HTTP endpoints |
| **Server-Sent Events (SSE)** | Real-time streaming |
| **gRPC** | Temporal server communication |
| **Model Context Protocol (MCP)** | External service integration |
| **Temporal Nexus** | Cross-workflow service calls |

---

### **🧪 Testing & Code Quality**

| Technology | Purpose |
|------------|---------|
| **pytest** | Test framework |
| **pytest-asyncio** | Async test support |
| **Black** | Code formatting |
| **isort** | Import sorting |
| **mypy** | Static type checking |
| **flake8/ruff** | Linting |

---

### **📦 Package Management & Build**

| Technology | Purpose |
|------------|---------|
| **uv** | Fast Python package manager |
| **pip/setuptools** | Package installation |
| **hatchling** | Build backend |
| **npm** | Frontend package management |

---

## 🎯 Mid-Level AI Engineer - Job Requirements

### **Position Overview**
We are seeking a Mid-Level AI Engineer to join our team building enterprise-grade AI agent platforms. You will work on developing durable AI workflow systems that orchestrate LLM-powered agents for real-world business applications.

---

### **Required Technical Skills**

#### **Core Programming (Must Have)**
- ✅ **Python 3.10+** (3+ years) - Proficient in async/await, type hints, decorators
- ✅ **FastAPI or Flask** - RESTful API development experience
- ✅ **Pydantic** - Data validation and settings management

#### **AI/ML Engineering (Must Have)**
- ✅ **LLM Integration** - Experience with OpenAI API, Azure OpenAI, or similar
- ✅ **Prompt Engineering** - Designing and optimizing prompts for LLMs
- ✅ **Agent/Agentic Patterns** - Understanding of ReAct, tool-calling, function calling
- ✅ **Embeddings & Vector Search** - Semantic similarity, embedding models

#### **Databases (Must Have)**
- ✅ **PostgreSQL** - SQL, query optimization
- ✅ **Redis** - Caching, pub/sub, streams
- ✅ One of: **Neo4j**, MongoDB, or similar NoSQL database

#### **Infrastructure (Must Have)**
- ✅ **Docker & Docker Compose** - Container management
- ✅ **Git** - Version control best practices

---

### **Preferred Technical Skills (Nice to Have)**

#### **Workflow Orchestration**
- 🌟 **Temporal.io** - Durable workflow engine (highly preferred)
- 🌟 Experience with workflow orchestration (Airflow, Prefect, Dagster, etc.)

#### **Advanced AI/ML**
- 🌟 **LiteLLM** - Multi-provider LLM abstraction
- 🌟 Experience building multi-agent systems
- 🌟 Knowledge of RAG (Retrieval-Augmented Generation) patterns
- 🌟 Understanding of intent classification and NLU systems

#### **Frontend & Full-Stack**
- 🌟 **React** with modern hooks
- 🌟 **Tailwind CSS** or similar utility-first CSS
- 🌟 **TypeScript/JavaScript**

#### **Cloud & Observability**
- 🌟 AWS services (S3, Lambda, ECS)
- 🌟 **OpenTelemetry** - Distributed tracing
- 🌟 Monitoring tools (Jaeger, Dynatrace, DataDog)

#### **Additional Technologies**
- 🌟 **GraphQL** or gRPC experience
- 🌟 **Server-Sent Events (SSE)** or WebSockets
- 🌟 Knowledge graphs (Neo4j, Cypher query language)
- 🌟 **pgvector** or similar vector database extensions

---

### **Qualifications**

- **Education**: Bachelor's degree in Computer Science, Engineering, or related field (or equivalent experience)
- **Experience**: 3-5 years of professional software engineering experience
- **AI/ML Focus**: 1+ years working with LLMs or NLP systems

---

### **Responsibilities**

- Design and implement AI agent workflows using Temporal and LLM integrations
- Build and maintain REST APIs with FastAPI for agent orchestration
- Develop intent mapping and slot-filling systems for conversational AI
- Integrate multiple LLM providers (OpenAI, Azure OpenAI) via unified abstractions
- Work with vector databases and embedding models for semantic search
- Implement real-time event streaming (SSE) for live workflow updates
- Write comprehensive tests and maintain code quality standards
- Collaborate with cross-functional teams on AI-powered product features
- Document APIs and architectural decisions

---

### **What Sets This Role Apart**

🚀 **Cutting-Edge Stack**: Work with the latest in AI orchestration - Temporal workflows + LLM agents  
🧠 **Real AI Engineering**: Not just prompting, but building durable, production-grade agent systems  
📊 **Enterprise Scale**: Handle complex multi-intent orchestration and knowledge graphs  
🔧 **Full-Stack AI**: From vector search to SSE streaming to React frontends

---

Would you like me to refine any section of this job requirements document or provide additional details about any specific technology in the stack?