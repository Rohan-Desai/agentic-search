import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies API calls to the FastAPI backend on :8000,
// so you can run `npm run dev` and `make run` side by side.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/documents": "http://localhost:8000",
      "/search": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
