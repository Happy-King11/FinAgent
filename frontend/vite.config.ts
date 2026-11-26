import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 本地请求通过代理访问 FastAPI，避免开发环境额外放宽 CORS。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8010", changeOrigin: true },
      "/health": { target: "http://localhost:8010", changeOrigin: true },
    },
  },
});
