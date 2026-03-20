import express from "express";
import type { Database } from "better-sqlite3";
import { requireLogin } from "../middlewares/auth";
import { createOllama } from "../lib/ollama";
import { ingestDirectory } from "../services/ingest.service";

export function createIngestRouter({ db }: { db: Database }): express.Router {
  const router = express.Router();

  const ollama = createOllama({
    baseUrl: process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434",
  });
  const embedModel = process.env.EMBED_MODEL || "nomic-embed-text";
  const rawDir = process.env.RAW_DIR || "./data/raw";
  const chunkSize = Number(process.env.CHUNK_SIZE || 1200);
  const overlap = Number(process.env.CHUNK_OVERLAP || 150);

  router.post("/ingest/demo", requireLogin, async (req, res) => {
    try {
      const log: string[] = [];
      const user = req.session.user!;
      const result = await ingestDirectory({
        db,
        ollama,
        rawDir,
        embedModel,
        chunkSize,
        overlap,
        log,
        auditCtx: { userId: user.id, clientId: user.clientId },
      });
      res.json({ ok: true, docs: result.docs, chunks: result.chunks, log });
    } catch (e) {
      const err = e as Error;
      res.status(500).json({ error: err.message || "ingest error" });
    }
  });

  return router;
}
