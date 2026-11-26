import { BookOpen, CircleAlert, FileOutput, ShieldCheck } from "lucide-react";
import type { ApiResponse, ConsultationData } from "../api/types";
import { JsonView, StatusBadge } from "./Feedback";

export function ResultPanel({ response }: { response: ApiResponse<ConsultationData> }) {
  const data = response.data;
  if (!data) return null;
  return (
    <section className="result-stack" aria-live="polite">
      <div className="result-heading"><div><span className="eyebrow">ANALYSIS RESULT</span><h2>咨询结果</h2></div><StatusBadge status={data.status} /></div>
      <article className="answer-card"><div className="card-icon"><FileOutput size={20} /></div><div><h3>结论与解释</h3><p className="answer-copy">{data.answer || "本次咨询未返回自然语言解释。"}</p></div></article>
      {data.result && <article className="data-card"><h3>确定性计算结果</h3><p className="muted">以下数值由后端 Finance Engine 返回，前端未进行重算或改写。</p><JsonView value={data.result} /></article>}
      {response.warnings.length > 0 && <article className="warning-card"><div className="section-title"><CircleAlert size={18} /><h3>风险提示</h3></div><ul>{response.warnings.map((item, index) => <li key={`${item.message}-${index}`}>{item.message}</li>)}</ul></article>}
      {response.compliance && <article className="data-card"><div className="section-title"><ShieldCheck size={18} /><h3>合规检查</h3></div><JsonView value={response.compliance} /></article>}
      {response.citations.length > 0 && <article className="data-card"><div className="section-title"><BookOpen size={18} /><h3>证据引用</h3></div>{response.citations.map((citation, index) => <JsonView key={index} value={citation} />)}</article>}
      <footer className="trace-row"><span>Case ID: {data.case_id}</span><span>Trace ID: {response.trace_id}</span></footer>
    </section>
  );
}
