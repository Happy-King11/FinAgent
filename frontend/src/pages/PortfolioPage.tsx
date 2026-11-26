import { useMutation } from "@tanstack/react-query";
import { Activity, PieChart } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../api/client";
import { ErrorNotice, JsonView, PageHeader } from "../components/Feedback";

export function PortfolioPage() {
  const [portfolioId, setPortfolioId] = useState("portfolio_demo");
  const [includeProfile, setIncludeProfile] = useState(false);
  const [risk, setRisk] = useState("medium");
  const diagnosis = useMutation({ mutationFn: () => api.createPortfolioDiagnosis({ portfolio_id: portfolioId, ...(includeProfile ? { risk_profile: { risk_level: risk, horizon_years: 5, liquidity_need: "中等", confirmed: true } } : {}) }) });
  return <>
    <PageHeader eyebrow="PORTFOLIO" title="组合诊断" description="诊断集中度、暴露和风险画像适配。该功能只读，不包含交易或调仓执行入口。" />
    <div className="portfolio-layout"><section className="panel compact-panel"><div className="section-title"><PieChart size={19} /><h2>诊断参数</h2></div>
      <form className="stack-form" onSubmit={(event: FormEvent) => { event.preventDefault(); if (portfolioId.trim()) diagnosis.mutate(); }}>
        <label><span>组合编号</span><input value={portfolioId} onChange={(event) => setPortfolioId(event.target.value)} /></label>
        <label className="check-field"><input type="checkbox" checked={includeProfile} onChange={(event) => setIncludeProfile(event.target.checked)} /><span><strong>本次附带已确认画像</strong><small>仅使用用户明确确认的数据。</small></span></label>
        {includeProfile && <label><span>风险等级</span><select value={risk} onChange={(event) => setRisk(event.target.value)}><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>}
        {diagnosis.error && <ErrorNotice error={diagnosis.error} />}
        <button className="primary-button" disabled={!portfolioId.trim() || diagnosis.isPending}>{diagnosis.isPending ? "诊断中…" : "开始诊断"}</button>
      </form></section>
      <section className="panel result-panel-placeholder"><Activity size={27} />{diagnosis.data?.data ? <><h2>诊断结果</h2><JsonView value={diagnosis.data.data} />{diagnosis.data.warnings.map((warning, index) => <p className="risk-copy" key={index}>{warning.message}</p>)}</> : <><h2>等待诊断</h2><p>服务端结果将在此完整呈现，前端不会重算集中度指标。</p></>}</section>
    </div>
  </>;
}
