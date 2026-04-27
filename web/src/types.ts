/* ── API response types matching FastAPI schemas ── */

export type ProcessingStatus =
  | "pending"
  | "extracting"
  | "analyzing"
  | "indexing"
  | "completed"
  | "failed";

export interface UploadResponse {
  document_id: string;
  filename: string;
  doc_type: string;
  status: ProcessingStatus;
  message: string;
}

export interface DocumentStatus {
  document_id: string;
  doc_type: string;
  status: ProcessingStatus;
  filename: string;
  uploaded_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  stages_completed: string[];
}

export interface KeyValuePair {
  key: string;
  value: string;
  confidence: number;
  page: number | null;
}

export interface ExtractedTable {
  table_id: number;
  headers: string[];
  rows: string[][];
  page: number | null;
}

export interface ExtractionResult {
  document_id: string;
  doc_type: string;
  source_filename: string;
  page_count: number;
  extracted_at: string;
  key_value_pairs: KeyValuePair[];
  tables: ExtractedTable[];
  raw_text: string;
  confidence_score: number;
  metadata: Record<string, unknown>;
}

export interface RiskItem {
  title: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  clause_reference: string | null;
  recommendation: string;
}

export interface AnalysisResult {
  document_id: string;
  doc_type: string;
  analyzed_at: string;
  summary: string;
  risks: RiskItem[];
  metadata: Record<string, unknown>;
}

export interface AnalysisResponse {
  document_id: string;
  doc_type: string;
  status: ProcessingStatus;
  extraction: ExtractionResult | null;
  analysis: AnalysisResult | null;
}

export interface SearchHit {
  id: string;
  content: string;
  score: number;
  doc_type: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  query: string;
  total: number;
  results: SearchHit[];
  offset: number;
  top: number;
}
