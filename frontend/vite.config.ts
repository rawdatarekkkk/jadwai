import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  // JADWAI_API_URL lets a second local stack (for example a demo database) run alongside.
  server: { proxy: { "/api": (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env.JADWAI_API_URL || "http://127.0.0.1:8010" } },
});
