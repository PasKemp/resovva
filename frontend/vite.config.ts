import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// BACKEND_URL: used by the Vite proxy to reach the FastAPI backend.
// In Docker this is "http://backend:8000" (set via docker-compose environment).
// Outside Docker (plain `npm run dev`) it falls back to localhost:8000.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals:     true,
    environment: "jsdom",
    setupFiles:  "./src/test/setup.ts",
  },
  appType: "spa", // enables SPA HTML fallback — unknown paths serve index.html without redirect
  server: {
    host: "0.0.0.0",   // listen on all interfaces → reachable from phone on local network
    port: 5173,
    proxy: {
      // Forward all /api/* calls to the FastAPI backend.
      // Because the phone also hits the Vite server, this proxy makes every
      // request same-origin from the browser's perspective → no CORS issues.
      "/api": {
        target:       backendUrl,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir:        "dist",
    sourcemap:     true,
    rollupOptions: {
      output: {
        // Split vendor chunks for better caching
        manualChunks: {
          react: ["react", "react-dom"],
        },
      },
    } as any,
  },
});
