const { cosine } = require("../lib/vector");

function loadAllChunks(db) {
  const rows = db.prepare(`
    SELECT c.id, c.source, c.doc_type, c.title, c.text, c.embedding_json,
           c.doc_id, c.doc_version, c.effective_date, c.jurisdiction,
           d.allowed_roles_json
    FROM chunks c
    LEFT JOIN docs d ON d.id = c.doc_row_id
  `).all();

  return rows.map((r) => ({
    id: r.id,
    source: r.source,
    docType: r.doc_type,
    title: r.title,
    text: r.text,
    embedding: JSON.parse(r.embedding_json),
    docId: r.doc_id || null,
    docVersion: r.doc_version || 1,
    effectiveDate: r.effective_date || null,
    jurisdiction: r.jurisdiction || null,
    allowedRoles: r.allowed_roles_json ? JSON.parse(r.allowed_roles_json) : ["user", "admin"],
  }));
}

function maxVersionByDoc(chunks) {
  const m = new Map();
  for (const c of chunks) {
    const k = c.docId || c.source;
    const cur = m.get(k);
    if (cur == null || c.docVersion > cur) m.set(k, c.docVersion);
  }
  return m;
}

function hasAccess(userRoles, allowedRoles) {
  if (!allowedRoles || !allowedRoles.length) return true;
  return userRoles.some((r) => allowedRoles.includes(r));
}

async function retrieve({ db, ollama, embedModel, query, topK = 6, userRoles = ["user"] }) {
  const qEmb = await ollama.embed({ model: embedModel, input: query });
  const all = loadAllChunks(db);

  // RBAC filter
  let candidates = all.filter((c) => hasAccess(userRoles, c.allowedRoles));

  // latest vs all
  const strategy = (process.env.DOC_VERSION_STRATEGY || "latest").toLowerCase();
  if (strategy === "latest") {
    const mv = maxVersionByDoc(candidates);
    candidates = candidates.filter((c) => {
      const k = c.docId || c.source;
      return c.docVersion === mv.get(k);
    });
  }

  const scored = candidates.map((d) => ({
    ...d,
    score: cosine(qEmb, d.embedding),
  }));

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}

module.exports = { retrieve };
