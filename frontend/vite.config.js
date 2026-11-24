import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, /v1/* goes to the API on port 8000, so the browser sees one origin
// and the API needs no CORS setting. Override with API_URL=... npm run dev
export default defineConfig({
  plugins: [react()],
  server: {
    // the example payloads live one folder up, in ../payloads (single source of truth)
    fs: { allow: [".."] },
    proxy: { "/v1": process.env.API_URL || "http://127.0.0.1:8000" },
  },
});
