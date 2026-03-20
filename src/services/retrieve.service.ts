import type { Database } from "better-sqlite3";
import { cosine } from "../lib/vector";
import type { OllamaClient } from "../lib/ollama";

export interface Chunk {
  id: number;
  source: string;
  docType: string;
  title: string | null;
  text: string;
  embedding: number[];
  docId: string | null;
  docVersion: number;
  effectiveDate: string | null;
  jurisdiction: string | null;
  allowedRoles: string[];
}

export interface ScoredChunk extends Chunk {
  score: number;
}

interface ChunkRow {
  id: number;
  source: string;
  doc_type: string;
  title: string | null;
  text: string;
  embedding_json: string;
  doc_id: string | null;
  doc_version: number | null;
  effective_date: string | null;
  jurisdiction: string | null;
  allowed_roles_json: string | null;
}

function loadAllChunks(db: Database): Chunk[] {
  const rows = db
    .prepare(
      `
    SELECT c.id, c.source, c.doc_type, c.title, c.text, c.embedding_json,
           c.doc_id, c.doc_version, c.effective_date, c.jurisdiction,
           d.allowed_roles_json
    FROM chunks c
    LEFT JOIN docs d ON d.id = c.doc_row_id
  `
    )
    .all() as ChunkRow[];

  return rows.map((r) => ({
    id: r.id,
    source: r.source,
    docType: r.doc_type,
    title: r.title,
    text: r.text,
    embedding: JSON.parse(r.embedding_json) as number[],
    docId: r.doc_id || null,
    docVersion: r.doc_version || 1,
    effectiveDate: r.effective_date || null,
    jurisdiction: r.jurisdiction || null,
    allowedRoles: r.allowed_roles_json
      ? (JSON.parse(r.allowed_roles_json) as string[])
      : ["user", "admin"],
  }));
}

function maxVersionByDoc(chunks: Chunk[]): Map<string, number> {
  const m = new Map<string, number>();
  for (const c of chunks) {
    const k = c.docId || c.source;
    const cur = m.get(k);
    if (cur == null || c.docVersion > cur) m.set(k, c.docVersion);
  }
  return m;
}

function hasAccess(userRoles: string[], allowedRoles: string[]): boolean {
  if (!allowedRoles || !allowedRoles.length) return true;
  return userRoles.some((r) => allowedRoles.includes(r));
}

export async function retrieve({
  db,
  ollama,
  embedModel,
  query,
  topK = 6,
  userRoles = ["user"],
}: {
  db: Database;
  ollama: OllamaClient;
  embedModel: string;
  query: string;
  topK?: number;
  userRoles?: string[];
}): Promise<ScoredChunk[]> {
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

  const scored: ScoredChunk[] = candidates.map((d) => ({
    ...d,
    score: cosine(qEmb, d.embedding),
  }));

  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, topK);
}
