import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  appType: "spa", // enables SPA HTML fallback — unknown paths serve index.html without redirect
  server: {
    port: 5173,
    proxy: {
      // Forward all /api/* calls to the FastAPI backend during dev
      "/api": {
        target:      "http://localhost:8000",
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
    },
  },
});
