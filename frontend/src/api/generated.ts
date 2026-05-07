export type KnowledgeScope = 'global' | 'session' | 'both'

export interface QueryRequestModel {
  query: string
  top_k?: number
  use_llm?: boolean
  use_rerank?: boolean
  stream?: boolean
  include_citations?: boolean
  provider?: string | null
  model?: string | null
  reranker_model?: string | null
  provider_api_key?: string | null
  session_id?: string | null
  knowledge_scope?: KnowledgeScope
}

export interface CitationModel {
  raw_id: string
  chunk_id: string
  resolved: boolean
  title?: string | null
  source?: string | null
  verification_score: number
  verification: string
}

export interface RetrievedChunkModel {
  id: string
  score: number
  source: string
  confidence: number
  metadata: Record<string, unknown>
  preview: string
}

export interface TruthfulnessModel {
  nli_faithfulness: number
  citation_groundedness: number
  uncited_claims: number
  score: number
}

export interface QueryResponseModel {
  query: string
  provider: string
  model: string
  answer: string
  processing_time_ms: number
  cached: boolean
  validation_issues: string[]
  citations: CitationModel[]
  retrieved: RetrievedChunkModel[]
  truthfulness?: TruthfulnessModel | null
}

export interface HealthModel {
  status: string
  collection: string
}

export interface MetricsModel {
  cache_ttl_seconds: number
  available_providers: string[]
}

export interface LlmConfigModel {
  default_provider: string
  default_model_by_provider: Record<string, string>
  allowed_models_by_provider: Record<string, string[]>
  provider_key_configured: Record<string, boolean>
  demo_mode: boolean
}
