export interface User {
  id: string;
  username: string;
  display_name: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface ChunkReference {
  chunk_id: string;
  doc_id: string;
  title: string;
  category: string;
  published: string;
  version: string;
  text_snippet: string;
  relevance_score?: number;
  verification_status?: 'verified' | 'conflict' | 'unverified';
}

export interface Claim {
  claim: string;
  supporting_chunk_ids: string[];
  confidence: 'high' | 'medium' | 'low' | 'none';
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  sources?: ChunkReference[];
  claims?: Claim[];
  limitations?: string[];
  needs_clarification?: boolean;
  agent_trace?: AgentTrace;
}

export interface AgentTrace {
  retrieval_query?: string;
  retrieved_chunk_ids?: string[];
  conflicts_detected?: boolean;
  memory_ops?: string[];
  llm_provider?: string;
  execution_ms?: number;
}

export interface Memory {
  id: string;
  user_id: string;
  category: 'preferences' | 'user_context' | 'active_projects' | 'decisions' | 'conversation_summaries';
  content: string;
  created_at: string;
  updated_at: string;
  confidence?: number;
  status: 'active' | 'corrected' | 'deleted';
  provenance?: string;
}

export interface HealthStatus {
  status: string;
  database: string;
  vector_store: string;
  llm: string;
  ingestion: string;
  langsmith: string;
}
