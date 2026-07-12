import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// The FastAPI backend (server.py) serves the built app from ../static and
// mounts it at /static, so we build there with a matching base path. During
// development, `npm run dev` proxies /api (including the SSE stream) to the
// running Python server on :8000.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/static/",
  build: {
    outDir: "../static",
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        // Server-Sent Events must not be buffered by the dev proxy.
        configure: (proxy) => {
          proxy.on("proxyRes", (proxyRes) => {
            if ((proxyRes.headers["content-type"] || "").includes("event-stream")) {
              proxyRes.headers["cache-control"] = "no-cache";
            }
          });
        },
      },
    },
  },
});
