const fs = require("fs");
const path = require("path");
const { chunkText } = require("../lib/chunker");
const { sha256 } = require("../lib/hash");
const { loadManifest } = require("./manifest.service");
const { parseLawMeta, parseCaseMeta } = require("./metadata_parser.service");
const { audit } = require("./audit.service");

function walkFiles(dir) {
  const out = [];
  const items = fs.readdirSync(dir, { withFileTypes: true });
  for (const it of items) {
    const p = path.join(dir, it.name);
    if (it.isDirectory()) out.push(...walkFiles(p));
    else if (it.isFile()) out.push(p);
  }
  return out;
}

function inferDocType(filepath) {
  const p = filepath.replace(/\\/g, "/");
  if (p.includes("/law/")) return "law";
  if (p.includes("/cases/")) return "case";
  return "misc";
}

function readTextFile(filepath) {
  const ext = path.extname(filepath).toLowerCase();
  const raw = fs.readFileSync(filepath);
  if (ext === ".md" || ext === ".txt") return raw.toString("utf-8");
  return raw.toString("utf-8");
}

/**
 * Final ingest:
 * - manifest docs -> docs table upsert
 * - chunks linked to docs via doc_row_id
 * - ACL stored per doc (allowed_roles_json)
 * - parsed meta stored in docs.meta_json
 */
async function ingestDirectory({ db, ollama, rawDir, embedModel, chunkSize, overlap, log, manifestPath = "data/manifest.json", auditCtx = null }) {
  const manifest = loadManifest(manifestPath);
  const docs = [];

  if (manifest?.documents?.length) {
    for (const d of manifest.documents) {
      docs.push({
        docId: d.doc_id,
        docType: d.doc_type,
        title: d.title,
        jurisdiction: d.jurisdiction || manifest.default?.jurisdiction || "KR",
        effectiveDate: d.effective_date || null,
        version: Number(d.version || 1),
        allowedRoles: d.allowed_roles || manifest.default?.allowed_roles || ["user", "admin"],
        absPath: path.join(process.cwd(), d.path),
        source: d.path.replace(/\\/g, "/"),
        extra: d,
      });
    }
    log.push(`[MANIFEST] loaded ${docs.length} docs from ${manifestPath}`);
  } else {
    const files = walkFiles(rawDir).filter((p) => [".md", ".txt"].includes(path.extname(p).toLowerCase()));
    for (const fp of files) {
      const rel = path.relative(process.cwd(), fp).replace(/\\/g, "/");
      const docType = inferDocType(fp);
      const docId = sha256(rel).slice(0, 12).toUpperCase();
      docs.push({
        docId: `DOC-${docId}`,
        docType,
        title: path.basename(fp),
        jurisdiction: "KR",
        effectiveDate: null,
        version: 1,
        allowedRoles: ["user", "admin"],
        absPath: fp,
        source: rel,
        extra: {},
      });
    }
    log.push(`[MANIFEST] not found. fallback walk: ${docs.length} files`);
  }

  if (!docs.length) {
    log.push(`[WARN] no ingestable docs`);
    return { ok: true, docs: 0, chunks: 0 };
  }

  // Upsert docs + replace chunks per doc/version
  const delChunksByDoc = db.prepare(`DELETE FROM chunks WHERE doc_id = ? AND doc_version = ?`);
  const delDoc = db.prepare(`DELETE FROM docs WHERE doc_id = ? AND doc_version = ?`);

  const insDoc = db.prepare(`
    INSERT INTO docs (
      doc_id, doc_version, doc_type, title, source, jurisdiction, effective_date,
      allowed_roles_json, meta_json, content_hash, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  const getDocRow = db.prepare(`SELECT id FROM docs WHERE doc_id = ? AND doc_version = ?`);

  const insChunk = db.prepare(`
    INSERT INTO chunks (
      source, doc_type, title, text, embedding_json, meta_json, created_at,
      doc_id, doc_version, effective_date, jurisdiction, content_hash, chunk_index, doc_row_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  let chunkTotal = 0;

  for (const d of docs) {
    if (!fs.existsSync(d.absPath)) {
      log.push(`[WARN] missing file: ${d.source}`);
      continue;
    }
    const text = readTextFile(d.absPath);
    const fileHash = sha256(text);

    // parse meta
    let parsed = {};
    if (d.docType === "law") parsed = parseLawMeta(text);
    if (d.docType === "case") parsed = { ...parseCaseMeta(text), ...parsed };

    const meta = { ...d.extra, parsed };

    // Replace doc row + related chunks for that doc/version
    delChunksByDoc.run(d.docId, d.version);
    delDoc.run(d.docId, d.version);

    insDoc.run(
      d.docId,
      d.version,
      d.docType,
      d.title || null,
      d.source,
      d.jurisdiction,
      d.effectiveDate,
      JSON.stringify(d.allowedRoles),
      JSON.stringify(meta),
      fileHash,
      new Date().toISOString()
    );

    const docRow = getDocRow.get(d.docId, d.version);
    const docRowId = docRow?.id;

    const chunks = chunkText(text, { chunkSize, overlap });
    log.push(`[DOC] ${d.docId}@v${d.version} roles=${d.allowedRoles.join(",")} ${d.source} -> ${chunks.length} chunks`);

    for (let idx = 0; idx < chunks.length; idx++) {
      const c = chunks[idx];
      const contentHash = sha256(`${d.docId}|${d.version}|${idx}|${c}`);
      const emb = await ollama.embed({ model: embedModel, input: c });

      const chunkMeta = {
        docId: d.docId,
        version: d.version,
        effectiveDate: d.effectiveDate,
        jurisdiction: d.jurisdiction,
        source: d.source,
        title: d.title,
        docType: d.docType,
        allowedRoles: d.allowedRoles,
        docRowId,
        chunkIndex: idx,
      };

      insChunk.run(
        d.source,
        d.docType,
        d.title,
        c,
        JSON.stringify(emb),
        JSON.stringify(chunkMeta),
        new Date().toISOString(),
        d.docId,
        d.version,
        d.effectiveDate,
        d.jurisdiction,
        contentHash,
        idx,
        docRowId
      );
      chunkTotal++;
    }
  }

  if (auditCtx) {
    audit(db, { ...auditCtx, eventType: "ingest_demo", payload: { docs: docs.length, chunks: chunkTotal } });
  }

  log.push(`[OK] ingest done. docs=${docs.length}, chunks=${chunkTotal}`);
  return { ok: true, docs: docs.length, chunks: chunkTotal };
}

module.exports = { ingestDirectory };
