import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Search, XCircle } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, JsonView, PageHeader } from "../components/Feedback";

export function AuditPage() {
  const [caseId, setCaseId] = useState("");
  const audit = useMutation({ mutationFn: () => api.getAudit(caseId) });
  return <>
    <PageHeader eyebrow="AUDIT" title="审计追踪" description="按咨询编号查看追加式事件链。读取该页面需要 audit:read 权限。" />
    <section className="panel"><form className="inline-form audit-search" onSubmit={(event: FormEvent) => { event.preventDefault(); if (caseId.trim()) audit.mutate(); }}><input value={caseId} onChange={(event) => setCaseId(event.target.value)} placeholder="输入 Case ID" aria-label="Case ID" /><button className="primary-button"><Search size={17} />查询</button></form>
      {audit.error && <ErrorNotice error={audit.error} />}
      {!audit.data && !audit.isPending && <EmptyState title="输入咨询编号" description="审计事件按写入顺序展示，并显示哈希链验证结果。" />}
      {audit.data?.data && <div className="audit-content"><div className={`chain-banner ${audit.data.data.chain_valid ? "valid" : "invalid"}`}>{audit.data.data.chain_valid ? <CheckCircle2 size={20} /> : <XCircle size={20} />}<strong>{audit.data.data.chain_valid ? "审计链验证通过" : "审计链验证失败"}</strong></div><div className="timeline">{audit.data.data.events.map((event, index) => <article key={index}><span className="timeline-index">{index + 1}</span><JsonView value={event} /></article>)}</div></div>}
    </section>
  </>;
}
