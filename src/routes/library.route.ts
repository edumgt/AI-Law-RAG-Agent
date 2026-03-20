import express from "express";
import type { Database } from "better-sqlite3";
import { requireLogin } from "../middlewares/auth";

interface ChunkRow {
  source: string;
  doc_type: string;
  title: string | null;
  doc_id: string | null;
  doc_version: number | null;
  effective_date: string | null;
  jurisdiction: string | null;
  text: string;
}

export function createLibraryRouter({ db }: { db: Database }): express.Router {
  const router = express.Router();

  router.get("/library/search", requireLogin, (req, res) => {
    const q = String(req.query?.q || "").trim();
    if (!q) return res.json({ ok: true, items: [] });

    const rows = (
      db
        .prepare(
          `
          SELECT source, doc_type, title, text, doc_id, doc_version, effective_date, jurisdiction
          FROM chunks
          WHERE text LIKE ?
          LIMIT 15
        `
        )
        .all("%" + q + "%") as ChunkRow[]
    ).map((r) => ({
      source: r.source,
      docType: r.doc_type,
      title: r.title,
      docId: r.doc_id || null,
      docVersion: r.doc_version || 1,
      effectiveDate: r.effective_date || null,
      jurisdiction: r.jurisdiction || null,
      text: r.text.length > 800 ? r.text.slice(0, 800) + "..." : r.text,
      score: 0.0,
    }));

    res.json({ ok: true, items: rows });
  });

  return router;
}
