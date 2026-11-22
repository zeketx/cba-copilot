import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type Plugin } from "vite";
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

function previewNotFoundPage(): Plugin {
  return {
    name: "preview-not-found-page",
    configurePreviewServer(server) {
      return () => {
        server.middlewares.use((req, res, next) => {
          if (req.method !== "GET" && req.method !== "HEAD") {
            next();
            return;
          }
          let pathname = "/";
          try {
            pathname = new URL(req.url ?? "/", "http://vite.local").pathname;
          } catch {
            next();
            return;
          }
          if (pathname === "/" || pathname === "/index.html") {
            next();
            return;
          }
          const notFound = path.resolve(
            server.config.root,
            server.config.build.outDir,
            "404.html",
          );
          if (!existsSync(notFound)) {
            next();
            return;
          }
          const headers = server.config.preview.headers;
          if (headers) {
            for (const [name, value] of Object.entries(headers)) {
              if (value !== undefined) {
                res.setHeader(name, value);
              }
            }
          }
          const html = readFileSync(notFound);
          res.statusCode = 404;
          res.setHeader("Content-Type", "text/html; charset=utf-8");
          res.setHeader("Content-Length", String(html.byteLength));
          res.end(req.method === "HEAD" ? undefined : html);
        });
      };
    },
  };
}

export default defineConfig(({ mode }) => {
  const config = {
    plugins: [react(), tailwindcss(), previewNotFoundPage()],
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
    // Railway serves `vite preview`. MPA turns off the SPA index.html fallback so unknown paths 404.
    appType: "mpa",
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
