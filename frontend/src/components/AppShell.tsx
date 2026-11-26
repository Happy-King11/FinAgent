import { useQuery } from "@tanstack/react-query";
import {
  BookOpenText, Boxes, BriefcaseBusiness, CircleUserRound, FileClock,
  Menu, MessageSquareText, Settings, ShieldCheck, X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "../api/client";

const navigation = [
  { to: "/consult", label: "智能咨询", icon: MessageSquareText },
  { to: "/knowledge", label: "知识与文档", icon: BookOpenText },
  { to: "/products", label: "产品中心", icon: Boxes },
  { to: "/profile", label: "风险画像", icon: CircleUserRound },
  { to: "/portfolio", label: "组合诊断", icon: BriefcaseBusiness },
  { to: "/audit", label: "审计追踪", icon: FileClock },
  { to: "/settings", label: "运行设置", icon: Settings },
];

export function AppShell() {
  const [menuOpen, setMenuOpen] = useState(false);
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });

  return (
    <div className="app-layout">
      <aside className={`sidebar ${menuOpen ? "is-open" : ""}`}>
        <div className="brand-row">
          <div className="brand-mark"><ShieldCheck size={23} /></div>
          <div><strong>FinAgent</strong><span>咨询与风控工作台</span></div>
          <button className="icon-button mobile-only" onClick={() => setMenuOpen(false)} aria-label="关闭菜单"><X size={20} /></button>
        </div>
        <nav className="nav-list" aria-label="主导航">
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setMenuOpen(false)} className={({ isActive }) => isActive ? "active" : ""}>
              <Icon size={19} /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className={`health-dot ${health.isSuccess ? "ok" : health.isError ? "bad" : ""}`} />
          <div><strong>{health.isSuccess ? "服务运行正常" : health.isError ? "服务连接失败" : "正在检查服务"}</strong><small>金融数值由确定性引擎生成</small></div>
        </div>
      </aside>
      {menuOpen && <button className="sidebar-backdrop" onClick={() => setMenuOpen(false)} aria-label="关闭导航" />}
      <main className="main-shell">
        <header className="topbar">
          <button className="icon-button mobile-only" onClick={() => setMenuOpen(true)} aria-label="打开菜单"><Menu size={21} /></button>
          <div><span className="eyebrow">INTERNAL PILOT</span></div>
          <div className="safety-label"><ShieldCheck size={16} /> 合规护栏已启用</div>
        </header>
        <div className="page-container"><Outlet /></div>
      </main>
    </div>
  );
}
