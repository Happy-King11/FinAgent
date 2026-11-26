# FinAgent 前端架构与技术选型

## 1. 目标与边界

前端面向内部试点金融咨询客服，覆盖八场景咨询、结果解释、风险与合规提示、证据引用、用户画像、适当性、组合诊断、文档知识和审计查看。

前端不计算或改写任何金融数字；估值、集中度、风险等级和适当性结论必须直接展示后端返回值。前端不提供交易、下单、转账或不可逆操作入口。

## 2. 技术选型

- React 19 + TypeScript 5：组件化 UI 与强类型接口契约。
- Vite 7：开发服务器、环境变量和生产构建。
- React Router 7：页面路由与浏览器历史。
- TanStack Query 5：API 请求、缓存、重试与失效控制。
- React Hook Form 7 + Zod 4：八场景动态表单与客户端输入校验。
- Lucide React：统一图标集。
- 原生 CSS Tokens：不依赖运行时 CSS 框架，便于企业品牌替换。

运行基线为 Node.js `>=20.19` 或 `>=22.12`。当前开发机 Node.js 24 可兼容运行；CI/容器建议固定 Node.js 22 LTS。所有依赖通过 `package-lock.json` 锁定。

## 3. 工程结构

```text
frontend/
  src/
    api/          HTTP 客户端、类型和接口函数
    components/   通用 UI 与金融结果组件
    features/     咨询、文档、画像、组合等业务模块
    pages/        路由页面
    styles/       Design Tokens 和全局样式
    App.tsx       应用路由与框架
    main.tsx      React/Query 根节点
  .env.example
  package.json
  vite.config.ts
```

## 4. 页面信息架构

- `/consult`：八场景咨询工作台，支持普通提问和估值结构化输入。
- `/knowledge`：上传授权文档、查询索引状态和知识检索。
- `/products`：授权产品列表与产品详情。
- `/profile`：风险画像编辑、版本控制和适当性检查。
- `/portfolio`：组合诊断与人工复核入口。
- `/audit`：按案例查看审计链，仅对有 `audit:read` 权限的主体开放。
- `/settings`：API 地址、开发身份和 Bearer Token 配置。

## 5. 状态与安全策略

- Bearer Token 仅保存在 `sessionStorage`，关闭标签页后自动清理。
- 开发身份使用 `X-Dev-Tenant-Id` / `X-Dev-User-Id`，生产构建默认隐藏该设置。
- 所有写请求自动生成 `Idempotency-Key`。
- `401` 清理会话并引导配置登录凭证；`403` 显示权限不足，不重试。
- TanStack Query 对读取型查询允许一次有限重试；写请求默认不自动重试，避免重复副作用，依赖后端幂等键安全重放。
- 页面必须区分 `blocked`、`human_review`、`waiting_confirmation`、`partial_success` 和 `completed`。
- 引用、风险、合规与缺失字段独立展示，不能只显示自然语言答案。

## 6. 视觉规范

视觉定位为企业级金融研究台：深墨色导航、暖白工作区、青绿色主操作、琥珀色风险提示。数字使用等宽数字特性，风险状态不只依赖颜色，同时提供图标和文字。桌面端采用双栏工作台，窄屏自动退化为单栏。

## 7. 构建与部署

开发环境通过 Vite Proxy 将 `/api` 和 `/health` 转发至 `http://localhost:8010`，避免本地 CORS 问题。生产环境使用 `VITE_API_BASE_URL` 指向网关地址；后端 CORS 必须显式允许前端域名。

```bash
cd frontend
npm install
npm run dev
npm run typecheck
npm run test
npm run build
```

