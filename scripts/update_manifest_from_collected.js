#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function readJsonl(fp) {
  if (!fs.existsSync(fp)) return [];
  const lines = fs.readFileSync(fp, "utf-8").split(/\r?\n/).filter(Boolean);
  return lines.map((l) => JSON.parse(l));
}

function loadManifest(fp) {
  if (!fs.existsSync(fp)) {
    return { schema: 1, default: { jurisdiction: "KR", language: "ko", version_strategy: "latest", allowed_roles: ["user","admin"] }, documents: [] };
  }
  return JSON.parse(fs.readFileSync(fp, "utf-8"));
}

function saveManifest(fp, m) {
  ensureDir(path.dirname(fp));
  fs.writeFileSync(fp, JSON.stringify(m, null, 2), "utf-8");
}

function key(doc) {
  return `${doc.doc_id}`;
}

function nextVersion(existingDocs, docId, effectiveDate) {
  const docs = existingDocs.filter(d => d.doc_id === docId);
  if (!docs.length) return 1;

  // If same effective_date exists, reuse its version (idempotent)
  const same = docs.find(d => String(d.effective_date || "") === String(effectiveDate || ""));
  if (same) return Number(same.version || 1);

  // Otherwise bump
  const maxV = Math.max(...docs.map(d => Number(d.version || 1)));
  return maxV + 1;
}

function main() {
  const index = readJsonl("data/collected/index.jsonl");
  const manifestPath = "data/manifest.json";
  const m = loadManifest(manifestPath);

  // Map existing docs for quick lookup
  const existing = m.documents || [];
  let added = 0;

  // We only add latest snapshot per doc_id+effective_date; multiple ingests are idempotent
  for (const d of index) {
    if (!d.doc_id || !d.doc_type || !d.path_md) continue;

    const v = nextVersion(existing, d.doc_id, d.effective_date || null);
    const pathMd = d.path_md.replace(/\\/g, "/");

    // skip if this exact doc_id+version already exists
    const already = existing.find(x => x.doc_id === d.doc_id && Number(x.version||1) === v);
    if (already) continue;

    existing.push({
      doc_id: d.doc_id,
      doc_type: d.doc_type,
      title: d.title,
      jurisdiction: d.jurisdiction || "KR",
      effective_date: d.effective_date || null,
      version: v,
      path: pathMd, // we ingest markdown as raw doc
      allowed_roles: ["user","admin"],
      source_url: d.source_url || null,
      meta: d.meta || {},
    });
    added++;
  }

  // Keep deterministic ordering: law then case, by doc_id then version
  existing.sort((a,b) => {
    const ta = a.doc_type.localeCompare(b.doc_type);
    if (ta !== 0) return ta;
    const ka = a.doc_id.localeCompare(b.doc_id);
    if (ka !== 0) return ka;
    return Number(a.version||1) - Number(b.version||1);
  });

  m.documents = existing;
  saveManifest(manifestPath, m);
  console.log(`[manifest] updated: added=${added} total=${existing.length}`);
}

main();
