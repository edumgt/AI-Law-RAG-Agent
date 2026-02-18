/**
 * NormalizedDoc schema (RAG-friendly)
 * {
 *   doc_id: string,
 *   doc_type: 'law'|'case'|'misc',
 *   title: string,
 *   jurisdiction: string, // e.g. KR
 *   effective_date: string|null, // YYYY-MM-DD
 *   version: number,
 *   source_url: string|null,
 *   body_md: string, // markdown body
 *   meta: object
 * }
 */
function assertNormalizedDoc(d) {
  if (!d || typeof d !== "object") throw new Error("doc is not object");
  if (!d.doc_id) throw new Error("missing doc_id");
  if (!d.doc_type) throw new Error("missing doc_type");
  if (!d.title) throw new Error("missing title");
  if (!d.jurisdiction) throw new Error("missing jurisdiction");
  if (typeof d.version !== "number") throw new Error("missing version");
  if (typeof d.body_md !== "string") throw new Error("missing body_md");
  return true;
}

module.exports = { assertNormalizedDoc };
