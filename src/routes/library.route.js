const express = require("express");
const { requireLogin } = require("../middlewares/auth");

function createLibraryRouter({ db }) {
  const router = express.Router();

  router.get("/library/search", requireLogin, (req, res) => {
    const q = String(req.query?.q || "").trim();
    if (!q) return res.json({ ok: true, items: [] });

    const rows = db
      .prepare(`
        SELECT source, doc_type, title, text, doc_id, doc_version, effective_date, jurisdiction
        FROM chunks
        WHERE text LIKE ?
        LIMIT 15
      `)
      .all("%" + q + "%")
      .map((r) => ({
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

module.exports = { createLibraryRouter };
