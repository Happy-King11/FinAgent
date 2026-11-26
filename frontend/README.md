# FinAgent Web

面向内部试点的 React 前端工作台。接口契约与页面边界见：

- [`backend/docs/FRONTEND_ARCHITECTURE.md`](../backend/docs/FRONTEND_ARCHITECTURE.md)
- [`backend/docs/FRONTEND_API_CONTRACT.md`](../backend/docs/FRONTEND_API_CONTRACT.md)

## 本地开发

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

打开 `http://localhost:5173`。Vite 会将 `/api` 和 `/health` 代理到已运行的后端 `http://localhost:8010`。

开发身份头默认关闭。仅在后端为 `APP_ENV=development` 且显式允许时，才可在“运行设置”中开启。

## 构建与检查

```powershell
npm run typecheck
npm run build
```

## Compose

根目录 Compose 增加了 `web` 服务，使用 `http://localhost:8080` 访问。Nginx 会把 API 请求转发到 Compose 内部的 `api:8000`。
