import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ClipboardCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Profile } from "../api/types";
import { ErrorNotice, JsonView, LoadingState, PageHeader, SuccessNotice } from "../components/Feedback";

export function ProfilePage() {
  const client = useQueryClient();
  const profile = useQuery({ queryKey: ["profile"], queryFn: api.getProfile });
  const [form, setForm] = useState<Required<Pick<Profile, "risk_level" | "horizon_years" | "liquidity_need" | "confirmed">>>({ risk_level: "medium", horizon_years: 5, liquidity_need: "中等", confirmed: false });
  useEffect(() => { if (profile.data?.data?.risk_level) setForm({ risk_level: profile.data.data.risk_level, horizon_years: profile.data.data.horizon_years ?? 5, liquidity_need: profile.data.data.liquidity_need ?? "中等", confirmed: Boolean(profile.data.data.confirmed) }); }, [profile.data]);
  const save = useMutation({ mutationFn: () => api.updateProfile(form, profile.data?.data?.version), onSuccess: () => client.invalidateQueries({ queryKey: ["profile"] }) });
  const [productRisk, setProductRisk] = useState("medium");
  const suitability = useMutation({ mutationFn: () => api.checkSuitability(productRisk) });

  return <>
    <PageHeader eyebrow="RISK PROFILE" title="风险画像与适当性" description="风险画像必须由用户明确确认；系统不会从对话中静默推断并覆盖已确认信息。" />
    {profile.isLoading && <LoadingState />}{profile.error && <ErrorNotice error={profile.error} />}
    <div className="two-column">
      <section className="panel"><div className="section-title"><ClipboardCheck size={19} /><h2>用户风险画像</h2></div>
        <form className="stack-form" onSubmit={(event: FormEvent) => { event.preventDefault(); save.mutate(); }}>
          <label><span>风险承受等级</span><select value={form.risk_level} onChange={(event) => setForm({ ...form, risk_level: event.target.value as "low" | "medium" | "high" })}><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
          <label><span>投资期限（年）</span><input type="number" min="0" max="100" value={form.horizon_years} onChange={(event) => setForm({ ...form, horizon_years: Number(event.target.value) })} /></label>
          <label><span>流动性需求</span><input value={form.liquidity_need} onChange={(event) => setForm({ ...form, liquidity_need: event.target.value })} /></label>
          <label className="check-field"><input type="checkbox" checked={form.confirmed} onChange={(event) => setForm({ ...form, confirmed: event.target.checked })} /><span><strong>我确认以上画像准确</strong><small>未确认的画像不能用于形成适当性结论。</small></span></label>
          {save.error && <ErrorNotice error={save.error} />}{save.isSuccess && <SuccessNotice>风险画像已更新。</SuccessNotice>}
          <button className="primary-button" disabled={save.isPending}>{save.isPending ? "保存中…" : "保存画像"}</button>
        </form>
      </section>
      <section className="panel"><div className="section-title"><CheckCircle2 size={19} /><h2>适当性检查</h2></div><p className="muted">将已确认画像与目标产品风险等级进行确定性比较。</p>
        <div className="stack-form"><label><span>产品风险等级</span><select value={productRisk} onChange={(event) => setProductRisk(event.target.value)}><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>
          <button className="secondary-button" onClick={() => suitability.mutate()} disabled={suitability.isPending}>{suitability.isPending ? "检查中…" : "执行适当性检查"}</button>
          {suitability.error && <ErrorNotice error={suitability.error} />}{suitability.data?.data && <JsonView value={suitability.data.data} />}
        </div>
      </section>
    </div>
  </>;
}
