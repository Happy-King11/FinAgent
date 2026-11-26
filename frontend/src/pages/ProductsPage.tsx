import { useQuery } from "@tanstack/react-query";
import { BadgeDollarSign, Droplets, ShieldAlert } from "lucide-react";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, LoadingState, PageHeader, StatusBadge } from "../components/Feedback";

export function ProductsPage() {
  const products = useQuery({ queryKey: ["products"], queryFn: api.listProducts });
  return <>
    <PageHeader eyebrow="PRODUCTS" title="产品中心" description="查看当前租户授权范围内的产品信息、费用、流动性与风险披露。" />
    {products.isLoading && <LoadingState label="正在加载产品" />}
    {products.error && <ErrorNotice error={products.error} />}
    {products.data?.data?.items.length === 0 && <EmptyState title="暂无产品" description="当前身份下没有可访问的产品记录。" />}
    <div className="product-grid">{products.data?.data?.items.map((product) => <article className="product-card" key={product.id}>
      <div className="product-card-head"><div className="card-icon"><BadgeDollarSign size={21} /></div><StatusBadge status={product.risk_level} /></div>
      <span className="eyebrow">{product.product_type ?? "FINANCIAL PRODUCT"}</span><h2>{product.name}</h2><p>{product.description ?? "暂无产品说明"}</p>
      <div className="product-meta"><div><Droplets size={16} /><span><small>流动性</small>{product.liquidity ?? "未提供"}</span></div><div><ShieldAlert size={16} /><span><small>风险等级</small>{product.risk_level ?? "未评级"}</span></div></div>
      {product.fees && <div className="fee-list">{product.fees.map((fee, index) => <span key={index}>{String(fee.name ?? "费用")}: <strong>{String(fee.value ?? "-")}</strong></span>)}</div>}
      {product.risk_disclosures?.map((item, index) => <p className="risk-copy" key={index}>{item}</p>)}
      <footer>ID · {product.id}</footer>
    </article>)}</div>
  </>;
}
