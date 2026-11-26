import { useMutation } from "@tanstack/react-query";
import { FilePlus2, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import { api } from "../api/client";
import { EmptyState, ErrorNotice, JsonView, PageHeader, SuccessNotice } from "../components/Feedback";

export function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const search = useMutation({ mutationFn: () => api.searchKnowledge(query) });
  const upload = useMutation({ mutationFn: () => api.createDocument({ title, content, source: "user_authorized" }), onSuccess: () => { setTitle(""); setContent(""); } });

  return <>
    <PageHeader eyebrow="KNOWLEDGE" title="知识与授权文档" description="检索租户范围内的可用证据，或提交已获授权的文本资料用于索引。" />
    <div className="two-column">
      <section className="panel">
        <div className="section-title"><Search size={19} /><h2>知识检索</h2></div>
        <form className="inline-form" onSubmit={(event) => { event.preventDefault(); if (query.trim()) search.mutate(); }}>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="输入主题、条款或关键词" aria-label="检索内容" />
          <button className="primary-button" disabled={!query.trim() || search.isPending}>{search.isPending ? "检索中…" : "检索"}</button>
        </form>
        {search.error && <ErrorNotice error={search.error} />}
        {!search.data && !search.isPending && <EmptyState title="等待检索" description="结果将包含文本片段和可追溯引用。" />}
        <div className="search-results">{search.data?.data?.results.map((item, index) => <article className="search-result" key={index}><span className="result-number">{String(index + 1).padStart(2, "0")}</span><p>{item.snippet}</p><JsonView value={item.citation} /></article>)}</div>
      </section>
      <section className="panel">
        <div className="section-title"><FilePlus2 size={19} /><h2>添加授权文档</h2></div>
        <form className="stack-form" onSubmit={(event: FormEvent) => { event.preventDefault(); if (title.trim() && content.trim()) upload.mutate(); }}>
          <label><span>文档标题</span><input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：产品说明书 2026 版" /></label>
          <label><span>文本内容</span><textarea rows={10} value={content} onChange={(event) => setContent(event.target.value)} placeholder="粘贴已获授权、允许进入本系统的文档文本" /></label>
          <p className="field-help">上传即表示你确认拥有处理该资料的权限。原始数据以服务端持久化记录为准。</p>
          {upload.error && <ErrorNotice error={upload.error} />}
          {upload.data && <SuccessNotice>文档已受理：{String(upload.data.data?.document_id ?? "")}</SuccessNotice>}
          <button className="secondary-button" disabled={!title.trim() || !content.trim() || upload.isPending}>{upload.isPending ? "正在提交…" : "提交并索引"}</button>
        </form>
      </section>
    </div>
  </>;
}
