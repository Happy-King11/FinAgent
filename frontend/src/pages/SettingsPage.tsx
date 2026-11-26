import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, Server, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { loadSettings, saveSettings } from "../api/client";
import type { AppSettings } from "../api/types";
import { PageHeader, SuccessNotice } from "../components/Feedback";

export function SettingsPage() {
  const queryClient = useQueryClient();
  const [settings, setSettings] = useState<AppSettings>(loadSettings);
  const [saved, setSaved] = useState(false);
  function update<K extends keyof AppSettings>(key: K, value: AppSettings[K]) { setSettings((current) => ({ ...current, [key]: value })); setSaved(false); }
  function submit(event: FormEvent) { event.preventDefault(); saveSettings(settings); queryClient.clear(); setSaved(true); }
  return <>
    <PageHeader eyebrow="RUNTIME" title="运行与身份设置" description="配置后端入口和当前会话凭据。生产环境应由组织身份系统签发短期 JWT。" />
    <div className="settings-layout"><form className="panel stack-form" onSubmit={submit}>
      <div className="section-title"><Server size={19} /><h2>服务连接</h2></div>
      <label><span>API Base URL</span><input value={settings.apiBaseUrl} onChange={(event) => update("apiBaseUrl", event.target.value)} placeholder="留空使用当前域名" /><small>本地 Vite 代理建议留空。</small></label>
      <div className="section-title subsection"><KeyRound size={19} /><h2>Bearer Token</h2></div>
      <label><span>访问令牌</span><textarea rows={4} value={settings.accessToken} onChange={(event) => update("accessToken", event.target.value)} placeholder="粘贴 JWT；仅保存于当前标签页会话" /></label>
      <label className="check-field"><input type="checkbox" checked={settings.enableDevIdentity} onChange={(event) => update("enableDevIdentity", event.target.checked)} /><span><strong>启用开发身份头</strong><small>只允许连接 development 模式后端。</small></span></label>
      {settings.enableDevIdentity && <div className="field-grid"><label><span>Tenant ID</span><input value={settings.tenantId} onChange={(event) => update("tenantId", event.target.value)} /></label><label><span>User ID</span><input value={settings.userId} onChange={(event) => update("userId", event.target.value)} /></label></div>}
      {saved && <SuccessNotice>设置已保存，查询缓存已清理。</SuccessNotice>}
      <button className="primary-button">保存当前会话设置</button>
    </form>
    <aside className="security-card"><ShieldCheck size={28} /><h2>安全边界</h2><ul><li>令牌不会写入 localStorage。</li><li>前端不会保存或计算金融结论。</li><li>开发身份头在生产环境必须关闭。</li><li>权限与租户隔离由后端最终裁决。</li></ul></aside></div>
  </>;
}
