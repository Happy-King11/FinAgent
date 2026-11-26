import { AlertCircle, CheckCircle2, FileSearch, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { ApiClientError } from "../api/client";

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="header-actions">{actions}</div>}</header>;
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return <div className="empty-state"><FileSearch size={28} /><strong>{title}</strong><p>{description}</p></div>;
}

export function LoadingState({ label = "正在加载" }: { label?: string }) {
  return <div className="loading-state"><LoaderCircle className="spin" size={20} />{label}</div>;
}

export function ErrorNotice({ error }: { error: unknown }) {
  const normalized = error instanceof ApiClientError ? error : new ApiClientError("UNKNOWN", error instanceof Error ? error.message : "发生未知错误", 0);
  return <div className="notice error" role="alert"><AlertCircle size={18} /><div><strong>{normalized.code}</strong><p>{normalized.message}</p></div></div>;
}

export function SuccessNotice({ children }: { children: ReactNode }) {
  return <div className="notice success"><CheckCircle2 size={18} /><div>{children}</div></div>;
}

export function StatusBadge({ status }: { status?: string | null }) {
  const value = status ?? "unknown";
  const positive = ["completed", "approved", "indexed", "ok"].includes(value);
  const warning = ["waiting_confirmation", "partial_success", "queued", "pending"].includes(value);
  return <span className={`status-badge ${positive ? "positive" : warning ? "warning" : ""}`}>{value.replaceAll("_", " ")}</span>;
}

export function JsonView({ value }: { value: unknown }) {
  return <pre className="json-view">{JSON.stringify(value, null, 2)}</pre>;
}
