const express = require("express");
const { requireLogin } = require("../middlewares/auth");
const { createOllama } = require("../lib/ollama");
const { ingestDirectory } = require("../services/ingest.service");

function createIngestRouter({ db }) {
  const router = express.Router();

  const ollama = createOllama({ baseUrl: process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434" });
  const embedModel = process.env.EMBED_MODEL || "nomic-embed-text";
  const rawDir = process.env.RAW_DIR || "./data/raw";
  const chunkSize = Number(process.env.CHUNK_SIZE || 1200);
  const overlap = Number(process.env.CHUNK_OVERLAP || 150);

  router.post("/ingest/demo", requireLogin, async (req, res) => {
    try {
      const log = [];
      const result = await ingestDirectory({
        db,
        ollama,
        rawDir,
        embedModel,
        chunkSize,
        overlap,
        log,
        auditCtx: { userId: req.session.user.id, clientId: req.session.user.clientId },
      });
      res.json({ ok: true, ...result, log });
    } catch (e) {
      res.status(500).json({ error: e.message || "ingest error" });
    }
  });

  return router;
}

module.exports = { createIngestRouter };
