#!/usr/bin/env node
require("dotenv").config();
const { initDb } = require("../services/db");
const { createOllama } = require("../lib/ollama");
const { ingestDirectory } = require("../services/ingest.service");

async function main() {
  const db = initDb(process.env.SQLITE_PATH || "./data/app.db");
  const ollama = createOllama({ baseUrl: process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434" });

  const log = [];
  const result = await ingestDirectory({
    db,
    ollama,
    rawDir: process.env.RAW_DIR || "./data/raw",
    embedModel: process.env.EMBED_MODEL || "nomic-embed-text",
    chunkSize: Number(process.env.CHUNK_SIZE || 1200),
    overlap: Number(process.env.CHUNK_OVERLAP || 150),
    log,
    manifestPath: process.env.MANIFEST_PATH || "data/manifest.json",
    auditCtx: null,
  });

  console.log(JSON.stringify({ result, log }, null, 2));
  process.exit(0);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
