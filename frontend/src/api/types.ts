export type SceneId =
  | "single_stock_research"
  | "product_explanation"
  | "financial_knowledge"
  | "portfolio_diagnosis"
  | "valuation_analysis"
  | "financial_statement_analysis"
  | "risk_assessment"
  | "compliance_consultation";

export type WarningItem = { code?: string; message: string };
export type Citation = Record<string, unknown>;

export interface ApiResponse<T> {
  request_id: string;
  trace_id: string;
  data: T | null;
  warnings: WarningItem[];
  citations: Citation[];
  compliance: Record<string, unknown> | null;
  error: { code: string; message: string } | null;
}

export interface ConsultationData {
  case_id: string;
  status: string;
  question?: string;
  answer?: string | null;
  intent?: string | null;
  result?: Record<string, unknown> | null;
  risk_assessment?: Record<string, unknown> | null;
}

export interface ConsultationRequest {
  question: string;
  requested_intent?: SceneId;
  scene_input?: Record<string, unknown>;
}

export interface Profile {
  risk_level?: "low" | "medium" | "high";
  horizon_years?: number;
  liquidity_need?: string;
  confirmed?: boolean;
  version?: number;
  [key: string]: unknown;
}

export interface Product {
  id: string;
  name: string;
  product_type?: string;
  risk_level?: string;
  fees?: Array<Record<string, unknown>>;
  liquidity?: string;
  description?: string;
  risk_disclosures?: string[];
  [key: string]: unknown;
}

export interface KnowledgeResult {
  snippet: string;
  citation: Citation;
}

export interface AppSettings {
  apiBaseUrl: string;
  accessToken: string;
  enableDevIdentity: boolean;
  tenantId: string;
  userId: string;
}
