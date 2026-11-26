import type { ApiResponse, AppSettings } from "./types";

const SETTINGS_KEY = "finagent.settings";

const environmentDefaults: AppSettings = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
  accessToken: "",
  enableDevIdentity: import.meta.env.VITE_ENABLE_DEV_IDENTITY === "true",
  tenantId: import.meta.env.VITE_DEV_TENANT_ID ?? "tenant-demo",
  userId: import.meta.env.VITE_DEV_USER_ID ?? "user-demo",
};

export class ApiClientError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly traceId?: string,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

export function loadSettings(): AppSettings {
  try {
    const saved = sessionStorage.getItem(SETTINGS_KEY);
    return saved ? { ...environmentDefaults, ...JSON.parse(saved) } : environmentDefaults;
  } catch {
    return environmentDefaults;
  }
}

export function saveSettings(settings: AppSettings): void {
  // JWT 仅进入 sessionStorage，关闭标签页后失效。
  sessionStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  window.dispatchEvent(new Event("finagent:settings"));
}

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/$/, "");
}

function errorDetail(body: unknown, status: number): ApiClientError {
  const payload = body as {
    detail?: string | { code?: string; message?: string };
    error?: { code?: string; message?: string };
    trace_id?: string;
  };
  const detail = payload?.detail;
  const structured = typeof detail === "object" ? detail : payload?.error;
  const message = structured?.message ?? (typeof detail === "string" ? detail : "请求失败，请稍后重试");
  return new ApiClientError(structured?.code ?? `HTTP_${status}`, message, status, payload?.trace_id);
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit & { idempotent?: boolean } = {},
): Promise<ApiResponse<T>> {
  const settings = loadSettings();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (settings.accessToken) headers.set("Authorization", `Bearer ${settings.accessToken}`);
  if (settings.enableDevIdentity) {
    headers.set("X-Dev-Tenant-Id", settings.tenantId);
    headers.set("X-Dev-User-Id", settings.userId);
  }
  if (init.idempotent) headers.set("Idempotency-Key", crypto.randomUUID());

  const response = await fetch(`${normalizeBaseUrl(settings.apiBaseUrl)}${path}`, { ...init, headers });
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new ApiClientError("INVALID_RESPONSE", "服务返回了无法解析的响应", response.status);
  }
  if (response.status === 401 && settings.accessToken) {
    // 令牌失效时清理当前会话，避免继续发送过期凭据。
    saveSettings({ ...settings, accessToken: "" });
  }
  if (!response.ok) throw errorDetail(body, response.status);
  const envelope = body as ApiResponse<T>;
  if (envelope.error) {
    throw new ApiClientError(envelope.error.code, envelope.error.message, response.status, envelope.trace_id);
  }
  return envelope;
}

export const api = {
  health: () => fetch(`${normalizeBaseUrl(loadSettings().apiBaseUrl)}/health/ready`).then(async (response) => {
    if (!response.ok) throw new ApiClientError("NOT_READY", "后端尚未就绪", response.status);
    return response.json() as Promise<Record<string, unknown>>;
  }),
  createConsultation: (payload: unknown) => apiRequest<import("./types").ConsultationData>("/api/v1/consultations", { method: "POST", body: JSON.stringify(payload), idempotent: true }),
  getConsultation: (id: string) => apiRequest<import("./types").ConsultationData>(`/api/v1/consultations/${encodeURIComponent(id)}`),
  appendMessage: (id: string, question: string) => apiRequest<import("./types").ConsultationData>(`/api/v1/consultations/${encodeURIComponent(id)}/messages`, { method: "POST", body: JSON.stringify({ question }), idempotent: true }),
  confirmConsultation: (id: string, confirmed = true) => apiRequest<import("./types").ConsultationData>(`/api/v1/consultations/${encodeURIComponent(id)}/confirm`, { method: "POST", body: JSON.stringify({ confirmed }), idempotent: true }),
  cancelConsultation: (id: string) => apiRequest<{ case_id: string; status: string }>(`/api/v1/consultations/${encodeURIComponent(id)}/cancel`, { method: "POST", idempotent: true }),
  searchKnowledge: (query: string, limit = 5) => apiRequest<{ results: import("./types").KnowledgeResult[] }>("/api/v1/knowledge/search", { method: "POST", body: JSON.stringify({ query, limit }) }),
  createDocument: (payload: { title: string; content: string; source: string }) => apiRequest<Record<string, unknown>>("/api/v1/documents", { method: "POST", body: JSON.stringify(payload) }),
  listProducts: () => apiRequest<{ items: import("./types").Product[] }>("/api/v1/products"),
  getProfile: () => apiRequest<import("./types").Profile>("/api/v1/users/me/profile"),
  updateProfile: (payload: import("./types").Profile, version?: number) => apiRequest<import("./types").Profile>("/api/v1/users/me/profile", { method: "PUT", body: JSON.stringify(payload), headers: version !== undefined ? { "If-Match": String(version) } : undefined }),
  checkSuitability: (risk: string) => apiRequest<Record<string, unknown>>("/api/v1/suitability/check", { method: "POST", body: JSON.stringify({ product_risk_level: risk }) }),
  createPortfolioDiagnosis: (payload: unknown) => apiRequest<Record<string, unknown>>("/api/v1/portfolio/diagnoses", { method: "POST", body: JSON.stringify(payload) }),
  getAudit: (caseId: string) => apiRequest<{ events: Array<Record<string, unknown>>; chain_valid: boolean }>(`/api/v1/audit/${encodeURIComponent(caseId)}`),
  createReport: (caseId: string) => apiRequest<Record<string, unknown>>("/api/v1/reports", { method: "POST", body: JSON.stringify({ case_id: caseId }) }),
};
