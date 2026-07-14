import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { Plugin } from "vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const forecastRoot = path.resolve(__dirname, "../data/forecast");

function forecastApiPlugin(): Plugin {
  const handler = (
    req: IncomingMessage,
    res: ServerResponse,
    next: (err?: unknown) => void,
  ) => {
    const url = req.url ?? "";
    if (!url.startsWith("/api/")) {
      next();
      return;
    }

    if (url === "/api/history" || url === "/api/history/") {
      const historyDir = path.join(forecastRoot, "history");
      if (!fs.existsSync(historyDir)) {
        res.statusCode = 200;
        res.setHeader("Content-Type", "application/json; charset=utf-8");
        res.end("[]");
        return;
      }
      const files = fs
        .readdirSync(historyDir)
        .filter((f: string) => f.endsWith(".json"))
        .sort();
      const items = files.map((name: string) => {
        const raw = fs.readFileSync(path.join(historyDir, name), "utf-8");
        const data = JSON.parse(raw) as {
          generated_at?: string;
          total_score?: number;
          direction?: string;
          confidence?: number;
          data_health?: number;
        };
        return {
          file: name,
          generated_at: data.generated_at ?? null,
          total_score: data.total_score ?? null,
          direction: data.direction ?? null,
          confidence: data.confidence ?? null,
          data_health: data.data_health ?? null,
        };
      });
      res.statusCode = 200;
      res.setHeader("Content-Type", "application/json; charset=utf-8");
      res.end(JSON.stringify(items));
      return;
    }

    const rel = decodeURIComponent(url.replace(/^\/api\//, "").split("?")[0] ?? "");
    if (rel.includes("..") || path.isAbsolute(rel)) {
      res.statusCode = 400;
      res.end("bad path");
      return;
    }
    const filePath = path.join(forecastRoot, rel);
    if (!filePath.startsWith(forecastRoot) || !fs.existsSync(filePath)) {
      res.statusCode = 404;
      res.end("not found");
      return;
    }
    if (!fs.statSync(filePath).isFile()) {
      res.statusCode = 404;
      res.end("not found");
      return;
    }
    res.statusCode = 200;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.end(fs.readFileSync(filePath));
  };

  return {
    name: "forecast-api",
    configureServer(server) {
      server.middlewares.use(handler);
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler);
    },
  };
}

export default defineConfig({
  plugins: [react(), forecastApiPlugin()],
  server: {
    port: 5173,
  },
});
