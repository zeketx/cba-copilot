import { readFileSync } from "node:fs";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import { securityHeaders } from "./security-headers.ts";

function officialPdfUrl(): string {
  const corpus = JSON.parse(
    readFileSync(path.resolve(__dirname, "../data/corpus.json"), "utf8"),
  ) as { pdf_url?: unknown };
  if (typeof corpus.pdf_url !== "string" || corpus.pdf_url === "") {
    throw new Error("data/corpus.json pdf_url must be a string");
  }
  return corpus.pdf_url;
}

// vite preview only answers these Host headers. Railway sets RAILWAY_PUBLIC_DOMAIN,
// and its healthcheck calls from healthcheck.railway.app.
function previewHosts(): string[] {
  const listed = (process.env.PREVIEW_ALLOWED_HOSTS ?? "").split(",");
  const hosts = [process.env.RAILWAY_PUBLIC_DOMAIN ?? "", ...listed]
    .map((host) => host.trim())
    .filter((host) => host !== "");
  if (hosts.length > 0) {
    hosts.push("healthcheck.railway.app");
  }
  return hosts;
}

export default defineConfig(({ mode }) => {
  const config = {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      proxy: {
        "/api": "http://127.0.0.1:8000",
      },
    },
  };
  if (mode !== "production") {
    return config;
  }
  const fileEnv = loadEnv(mode, __dirname, "VITE_");
  return {
    ...config,
    preview: {
      allowedHosts: previewHosts(),
      headers: securityHeaders({
        supabaseUrl: process.env.VITE_SUPABASE_URL || fileEnv.VITE_SUPABASE_URL,
        apiBase: process.env.VITE_API_BASE || fileEnv.VITE_API_BASE,
        pdfUrl: officialPdfUrl(),
      }),
    },
  };
});
