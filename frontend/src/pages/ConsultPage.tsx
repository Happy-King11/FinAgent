import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, Ban, BarChart3, BookOpenText, Building2, Check, FileCheck2, Gauge, Landmark, PieChart, Send, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { api } from "../api/client";
import type { ApiResponse, ConsultationData, SceneId } from "../api/types";
import { ErrorNotice, PageHeader, SuccessNotice } from "../components/Feedback";
import { ResultPanel } from "../components/ResultPanel";

const scenes: Array<{ id: SceneId; label: string; description: string; icon: typeof BarChart3 }> = [
  { id: "single_stock_research", label: "单股研究", description: "公司与证券证据梳理", icon: Building2 },
  { id: "product_explanation", label: "产品解读", description: "条款、费用与风险说明", icon: Landmark },
  { id: "financial_knowledge", label: "金融知识", description: "基于授权文档的问答", icon: BookOpenText },
  { id: "portfolio_diagnosis", label: "组合诊断", description: "集中度与风险适配", icon: PieChart },
  { id: "valuation_analysis", label: "估值分析", description: "DCF 等确定性计算", icon: BarChart3 },
  { id: "financial_statement_analysis", label: "财报分析", description: "指定报告期分析", icon: FileCheck2 },
  { id: "risk_assessment", label: "风险评估", description: "主体风险分级", icon: Gauge },
  { id: "compliance_consultation", label: "合规咨询", description: "规则边界与提示", icon: ShieldAlert },
];

const schema = z.object({
  question: z.string().trim().min(1, "请输入咨询问题").max(10_000),
  primary: z.string().trim().optional(),
  secondary: z.string().trim().optional(),
  source: z.enum(["user_supplied", "authorized_document", "dev_fixture"]),
  cashFlows: z.string().trim().optional(),
  wacc: z.string().trim().optional(),
  terminalGrowth: z.string().trim().optional(),
  netDebt: z.string().trim().optional(),
  shares: z.string().trim().optional(),
});
type FormValues = z.infer<typeof schema>;

function required(value: string | undefined, label: string): string {
  if (!value) throw new Error(`请填写${label}`);
  return value;
}

function numberValue(value: string | undefined, label: string): number {
  const parsed = Number(required(value, label));
  if (!Number.isFinite(parsed)) throw new Error(`${label}必须是有效数字`);
  return parsed;
}

function buildSceneInput(scene: SceneId, values: FormValues): Record<string, unknown> {
  const base = { scene, source_ids: [values.source] };
  switch (scene) {
    case "single_stock_research": return { ...base, security_id: required(values.primary, "证券代码") };
    case "product_explanation": return { ...base, ...(values.primary ? { product_id: values.primary } : {}) };
    case "financial_knowledge": return { ...base, topic: required(values.primary, "知识主题") };
    case "portfolio_diagnosis": return { ...base, portfolio_ref: required(values.primary, "组合编号"), confirmed_risk_profile: values.secondary === "true" };
    case "financial_statement_analysis": return { ...base, security_id: required(values.primary, "证券代码"), reporting_period: required(values.secondary, "报告期") };
    case "risk_assessment": return { ...base, subject_type: required(values.primary, "评估主体") };
    case "compliance_consultation": return { ...base, rule_topic: required(values.primary, "规则主题") };
    case "valuation_analysis": {
      const cashFlows = required(values.cashFlows, "自由现金流").split(/[,，\s]+/).filter(Boolean).map(Number);
      if (cashFlows.some((item) => !Number.isFinite(item))) throw new Error("自由现金流应为逗号分隔的数字");
      return {
        ...base, currency: required(values.primary, "币种"), period: required(values.secondary, "估值期间"),
        dcf: {
          free_cash_flows: cashFlows,
          wacc: numberValue(values.wacc, "WACC"),
          terminal_growth: numberValue(values.terminalGrowth, "永续增长率"),
          net_debt: numberValue(values.netDebt || "0", "净负债"),
          shares_outstanding: numberValue(values.shares, "总股本"),
        },
      };
    }
  }
}

function SceneFields({ scene, register }: { scene: SceneId; register: ReturnType<typeof useForm<FormValues>>["register"] }) {
  if (scene === "valuation_analysis") return <div className="field-grid valuation-fields">
    <label><span>币种</span><input {...register("primary")} placeholder="CNY" /></label>
    <label><span>估值期间</span><input {...register("secondary")} placeholder="FY2026" /></label>
    <label className="span-2"><span>自由现金流序列</span><input {...register("cashFlows")} placeholder="100, 110, 120" /></label>
    <label><span>WACC</span><input {...register("wacc")} inputMode="decimal" placeholder="0.10" /></label>
    <label><span>永续增长率</span><input {...register("terminalGrowth")} inputMode="decimal" placeholder="0.03" /></label>
    <label><span>净负债</span><input {...register("netDebt")} inputMode="decimal" placeholder="0" /></label>
    <label><span>总股本</span><input {...register("shares")} inputMode="decimal" placeholder="100" /></label>
  </div>;
  if (scene === "risk_assessment") return <div className="field-grid"><label><span>评估主体</span><select {...register("primary")}><option value="user">用户</option><option value="product">产品</option><option value="security">证券</option><option value="portfolio">组合</option><option value="consultation">咨询</option></select></label></div>;
  if (scene === "portfolio_diagnosis") return <div className="field-grid"><label><span>组合编号</span><input {...register("primary")} placeholder="portfolio_demo" /></label><label><span>风险画像状态</span><select {...register("secondary")}><option value="false">尚未确认</option><option value="true">已确认</option></select></label></div>;
  if (scene === "financial_statement_analysis") return <div className="field-grid"><label><span>证券代码</span><input {...register("primary")} placeholder="600000.SH" /></label><label><span>报告期</span><input {...register("secondary")} placeholder="FY2025" /></label></div>;
  const labels: Partial<Record<SceneId, [string, string]>> = {
    single_stock_research: ["证券代码", "600000.SH"], product_explanation: ["产品编号（可选）", "product-demo-fund"],
    financial_knowledge: ["知识主题", "什么是久期风险"], compliance_consultation: ["规则主题", "适当性销售边界"],
  };
  const [label, placeholder] = labels[scene] ?? ["业务标识", "请输入"];
  return <div className="field-grid"><label><span>{label}</span><input {...register("primary")} placeholder={placeholder} /></label></div>;
}

function CaseActions({ result, onResult }: { result: ApiResponse<ConsultationData>; onResult: (value: ApiResponse<ConsultationData>) => void }) {
  const [question, setQuestion] = useState("");
  const append = useMutation({ mutationFn: () => api.appendMessage(result.data!.case_id, question), onSuccess: onResult });
  const confirm = useMutation({ mutationFn: () => api.confirmConsultation(result.data!.case_id), onSuccess: onResult });
  const cancel = useMutation({ mutationFn: () => api.cancelConsultation(result.data!.case_id) });
  const report = useMutation({ mutationFn: () => api.createReport(result.data!.case_id) });
  const canContinue = !["cancelled", "blocked", "expired"].includes(result.data?.status ?? "");
  return <section className="panel case-actions"><div><span className="eyebrow">CASE CONTROLS</span><h2>继续处理此咨询</h2><p className="muted">所有状态变化会在服务端写入审计链；不可逆交易动作不在此系统范围内。</p></div>
    {canContinue && <div className="action-row"><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="追加一个追问" /><button className="secondary-button" disabled={!question.trim() || append.isPending} onClick={() => append.mutate()}><Send size={16} />追加消息</button></div>}
    <div className="action-row compact-actions">{result.data?.status === "waiting_confirmation" && <button className="secondary-button" disabled={confirm.isPending} onClick={() => confirm.mutate()}><Check size={16} />确认继续</button>}{canContinue && <button className="danger-button" disabled={cancel.isPending} onClick={() => cancel.mutate()}><Ban size={16} />取消咨询</button>}<button className="secondary-button" disabled={report.isPending} onClick={() => report.mutate()}><FileCheck2 size={16} />生成报告</button></div>
    {append.error && <ErrorNotice error={append.error} />}{confirm.error && <ErrorNotice error={confirm.error} />}{cancel.error && <ErrorNotice error={cancel.error} />}{report.error && <ErrorNotice error={report.error} />}{report.data && <SuccessNotice>报告已生成：{String(report.data.data?.report_id ?? "")}</SuccessNotice>}
  </section>;
}

export function ConsultPage() {
  const [scene, setScene] = useState<SceneId>("single_stock_research");
  const [result, setResult] = useState<ApiResponse<ConsultationData> | null>(null);
  const [localError, setLocalError] = useState<Error | null>(null);
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { source: "user_supplied", primary: "", secondary: "", question: "", netDebt: "0" } });
  const mutation = useMutation({ mutationFn: api.createConsultation, onSuccess: setResult });

  function chooseScene(next: SceneId) {
    setScene(next);
    setLocalError(null);
    form.reset({ source: "user_supplied", primary: next === "risk_assessment" ? "user" : "", secondary: next === "portfolio_diagnosis" ? "false" : "", question: "", netDebt: "0" });
  }

  const submit = form.handleSubmit((values) => {
    try {
      setLocalError(null);
      mutation.mutate({ question: values.question, requested_intent: scene, scene_input: buildSceneInput(scene, values) });
    } catch (error) {
      setLocalError(error instanceof Error ? error : new Error("输入无效"));
    }
  });

  const active = scenes.find((item) => item.id === scene)!;
  return <>
    <PageHeader eyebrow="CONSULTATION" title="金融咨询工作台" description="选择业务场景并提供明确输入。风险提示、证据引用与确定性计算结果将随响应一并展示。" />
    <div className="consult-layout">
      <section className="scene-panel">
        <div className="section-kicker"><span>01</span><div><h2>选择场景</h2><p>八类受控业务入口</p></div></div>
        <div className="scene-grid">{scenes.map(({ id, label, description, icon: Icon }) => <button type="button" key={id} className={`scene-card ${scene === id ? "selected" : ""}`} onClick={() => chooseScene(id)}><Icon size={20} /><strong>{label}</strong><small>{description}</small></button>)}</div>
      </section>
      <form className="consult-form panel" onSubmit={submit}>
        <div className="section-kicker"><span>02</span><div><h2>{active.label}</h2><p>{active.description}</p></div></div>
        <SceneFields scene={scene} register={form.register} />
        <label className="block-field"><span>数据来源</span><select {...form.register("source")}><option value="user_supplied">用户提供</option><option value="authorized_document">授权文档</option><option value="dev_fixture">开发样例（仅开发环境）</option></select></label>
        <label className="block-field"><span>咨询问题</span><textarea {...form.register("question")} rows={5} placeholder="请描述希望分析的问题、边界和期望输出……" /><small className="field-help">请勿输入身份证号、银行卡号等不必要的敏感信息。</small></label>
        {form.formState.errors.question && <p className="field-error">{form.formState.errors.question.message}</p>}
        {(localError || mutation.error) && <ErrorNotice error={localError || mutation.error} />}
        <button className="primary-button submit-button" disabled={mutation.isPending}>{mutation.isPending ? "正在执行合规与分析流程…" : <><Send size={17} />提交咨询<ArrowRight size={17} /></>}</button>
      </form>
    </div>
    {result && <><ResultPanel response={result} /><CaseActions result={result} onResult={setResult} /></>}
  </>;
}
