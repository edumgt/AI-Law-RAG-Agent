/**
 * NormalizedDoc schema (RAG-friendly)
 */
export interface NormalizedDoc {
  doc_id: string;
  doc_type: "law" | "case" | "misc";
  title: string;
  jurisdiction: string;
  effective_date: string | null;
  version: number;
  source_url: string | null;
  body_md: string;
  meta: Record<string, unknown>;
}

export function assertNormalizedDoc(d: unknown): d is NormalizedDoc {
  if (!d || typeof d !== "object") throw new Error("doc is not object");
  const doc = d as Record<string, unknown>;
  if (!doc.doc_id) throw new Error("missing doc_id");
  if (!doc.doc_type) throw new Error("missing doc_type");
  if (!doc.title) throw new Error("missing title");
  if (!doc.jurisdiction) throw new Error("missing jurisdiction");
  if (typeof doc.version !== "number") throw new Error("missing version");
  if (typeof doc.body_md !== "string") throw new Error("missing body_md");
  return true;
}
