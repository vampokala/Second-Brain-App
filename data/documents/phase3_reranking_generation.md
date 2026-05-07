# Phase 3: Reranking & Generation (Week 3-4)  
## Cross-encoder Reranking + RAG Response Generation

### 🎯 Phase Objectives
- Implement cross-encoder reranking for precision improvement
- Build RAG response generation pipeline
- Create context optimization and prompt engineering
- Add response quality evaluation
- Implement streaming response capability

### 📋 Deliverables Checklist
- [ ] Cross-encoder reranking system
- [ ] RAG response generation pipeline
- [ ] Context window optimization
- [ ] Prompt template management
- [ ] Response streaming implementation
- [ ] Generation quality metrics
- [ ] Response caching system

### 🛠 Technical Implementation

#### 1. Cross-encoder Reranking (Day 1-3)
**File**: `src/core/reranker.py`
**Features**:
- Multiple cross-encoder model support
- Batch processing for efficiency
- Score calibration and normalization
- Query-document pair optimization
- Confidence threshold filtering

```python
class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)
        self.batch_size = 32
        self.score_threshold = 0.1
    
    def rerank(self, query: str, documents: List[Document], top_k: int = 5) -> List[RankedDocument]:
        # Create query-document pairs
        # Batch process through cross-encoder
        # Calibrate and normalize scores
        # Filter by confidence threshold
        # Return top-k reranked results
        pass
    
    def batch_score(self, pairs: List[Tuple[str, str]]) -> List[float]:
        # Efficient batch scoring
        pass
```

#### 2. Context Optimization (Day 4-5)
**File**: `src/core/context_optimizer.py`
**Features**:
- Dynamic context window management
- Document chunking for large contexts
- Relevance-based prioritization
- Token counting and optimization
- Context compression techniques

```python
class ContextOptimizer:
    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens
        self.tokenizer = AutoTokenizer.from_pretrained("gpt2")
    
    def optimize_context(self, query: str, documents: List[Document]) -> OptimizedContext:
        # Count tokens for query and documents
        # Prioritize by relevance scores
        # Truncate or summarize if needed
        # Ensure coherent context flow
        pass
    
    def compress_document(self, document: Document, max_tokens: int) -> Document:
        # Extractive summarization for long docs
        pass
```

#### 3. Prompt Engineering System (Day 6-7)
**File**: `src/core/prompt_manager.py`
**Features**:
- Template-based prompt construction
- Dynamic prompt adaptation based on query type
- Few-shot example management
- Instruction fine-tuning support
- A/B testing for prompt variants

```python
class PromptManager:
    def __init__(self, template_path: str = "config/prompts/"):
        self.templates = self.load_templates(template_path)
        self.examples = self.load_examples()
    
    def build_prompt(self, query: str, context: List[Document], query_type: str = "factual") -> str:
        # Select appropriate template
        # Insert context and query
        # Add relevant examples
        # Apply formatting rules
        pass
    
    def get_system_prompt(self, query_type: str) -> str:
        # Return optimized system prompt
        pass
```

#### 4. RAG Generator Core (Day 8-10)
**File**: `src/core/generator.py`
**Features**:
- Integration with Ollama API
- Streaming response support
- Temperature and parameter control
- Response validation and filtering
- Error handling and fallbacks

```python
class RAGGenerator:
    def __init__(self, model_name: str = "qwen2.5-coder:14b"):
        self.model_name = model_name
        self.ollama_client = OllamaClient()
        self.prompt_manager = PromptManager()
    
    def generate(self, query: str, context: List[Document], stream: bool = False) -> GenerationResult:
        # Build optimized prompt
        # Generate response via Ollama
        # Validate response quality
        # Extract citations if present
        pass
    
    def generate_stream(self, query: str, context: List[Document]) -> Iterator[str]:
        # Streaming response generation
        pass
    
    def validate_response(self, response: str, context: List[Document]) -> ValidationResult:
        # Check for hallucinations
        # Verify factual consistency
        # Ensure appropriate tone
        pass
```

#### 5. Response Post-processing (Day 11-12)
**File**: `src/core/response_processor.py`
**Features**:
- Citation extraction and formatting
- Response quality scoring
- Factual consistency checking
- Response length optimization
- Markdown formatting for web display

#### 6. Generation Quality Metrics (Day 13)
**File**: `src/evaluation/generation_metrics.py`
**Metrics**:
- BLEU, ROUGE, BERTScore for reference-based evaluation
- Faithfulness scoring against source documents
- Relevance scoring for query alignment
- Citation accuracy and coverage
- Response coherence and fluency

#### 7. Caching & Performance (Day 14)
**Features**:
- Response caching with TTL
- Context similarity detection for cache hits
- Streaming response optimization
- Memory management for large contexts
- Async generation support

### 🔧 New Dependencies
```txt
# Reranking and generation
transformers>=4.30.0
torch>=2.0.0
sentence-transformers>=2.2.0
accelerate>=0.20.0
tokenizers>=0.13.0
rouge-score>=0.1.2
bert-score>=0.3.13
sacrebleu>=2.3.0
```

### 📊 Success Criteria
- [ ] Reranking improves Precision@5 by >15%
- [ ] Generation latency < 5 seconds for 95% of queries
- [ ] Response faithfulness score > 0.85
- [ ] Citation coverage > 90% of factual claims
- [ ] Streaming responses start within 1 second

### 🧪 Testing Strategy
1. **Reranking Quality**: A/B test with/without reranking
2. **Generation Quality**: Human evaluation on sample queries
3. **Citation Accuracy**: Manual verification of source claims
4. **Performance Tests**: Latency, throughput, memory usage
5. **Edge Cases**: Long queries, missing context, ambiguous questions

### 🎯 Prompt Templates
**Factual Query Template**:
```
You are a helpful assistant that answers questions based on provided documents. 
Always cite your sources and be precise in your answers.

Context Documents:
{context}

Question: {query}

Instructions:
- Answer based only on the provided context
- Include citations in [Doc X] format
- If information is not in the context, say so clearly
- Be concise but comprehensive

Answer:
```

**Exploratory Query Template**:
```
You are a knowledgeable assistant helping explore a topic using provided documents.
Provide a thoughtful analysis while staying grounded in the sources.

Context Documents:
{context}

Question: {query}

Instructions:
- Synthesize information from multiple sources when relevant
- Highlight different perspectives if they exist
- Use citations to support key points
- Suggest follow-up questions if appropriate

Analysis:
```

### ⏭ Phase 3 → Phase 4 Handoff
**Phase 3 Output**:
- High-quality generated responses with initial citations
- Response quality benchmarks
- Optimized prompt templates
- Performance metrics for generation pipeline

**Phase 4 Input Requirements**:
- Generated responses with embedded citations
- Source document mappings
- Confidence scores for generated content
- Response metadata for citation tracking