export interface ApiResponse<T = unknown> {
  code: number;
  data: T;
}

export interface ApiErrorBody {
  code: number;
  message: string;
  detail?: unknown;
}

export interface HealthData {
  status: "healthy" | "degraded" | "unavailable";
  chromadb: string;
  sqlite: string;
  embedding: string;
  llm: string;
}

export interface DocumentItem {
  id: number;
  filename: string;
  file_path: string;
  status: string;
  chunk_count: number;
  course: string;
  created_at: string;
}

export interface DocumentListData {
  items: DocumentItem[];
  total: number;
}

export interface DocumentUploadData {
  doc_id: number;
  filename: string;
  status: string;
  stored_path: string;
}

export interface Citation {
  source_file: string;
  page?: number | null;
  snippet: string;
  score: number;
}

export interface AskResult {
  answer: string;
  citations: Citation[];
  grounded: boolean;
}

export interface SettingsEffects {
  hot_reload: string[];
  restart_required: string[];
  notes: string[];
}

export interface AppConfigData {
  llm: {
    model: string;
    base_url: string;
    timeout: number;
    configured: boolean;
  };
  embedding: {
    provider: string;
    model: string;
    base_url: string;
    timeout: number;
    configured: boolean;
    uses_separate_credentials: boolean;
  };
  retrieval: {
    top_k: number;
    score_threshold: number;
  };
  chunk: {
    chunk_size: number;
    chunk_overlap: number;
  };
  storage: {
    knowledge_dir: string;
  };
  parsing: {
    pdf_use_ocr: boolean;
    pdf_force_ocr: boolean;
    pdf_ocr_language: string;
  };
  server: {
    host: string;
    port: number;
  };
  app: {
    max_upload_mb: number;
    debug: boolean;
  };
  proxy: {
    url: string;
    no_proxy: string;
    enabled: boolean;
  };
  meta: {
    config_path: string;
    env_writable: boolean;
  };
  health: {
    llm: string;
    embedding: string;
  };
  settings_effects?: SettingsEffects;
}

export interface ConfigUpdateRequest {
  llm?: {
    api_key?: string;
    base_url?: string;
    model?: string;
    timeout?: number;
  };
  embedding?: {
    provider?: "local" | "openai";
    api_key?: string;
    base_url?: string;
    model?: string;
    timeout?: number;
  };
  retrieval?: {
    top_k?: number;
    score_threshold?: number;
  };
  chunk?: {
    chunk_size?: number;
    chunk_overlap?: number;
  };
  parsing?: {
    pdf_use_ocr?: boolean;
    pdf_force_ocr?: boolean;
    pdf_ocr_language?: string;
  };
  app?: {
    max_upload_mb?: number;
  };
  server?: {
    host?: string;
    port?: number;
  };
  proxy?: {
    url?: string;
    no_proxy?: string;
  };
}
