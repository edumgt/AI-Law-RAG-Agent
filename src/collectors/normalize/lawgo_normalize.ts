import { assertNormalizedDoc, NormalizedDoc } from "../core/schema";

/**
 * Normalize for law.go style JSON payloads.
 * We accept flexible shapes and extract best-effort fields.
 */
function toIsoDate(x: unknown): string | null {
  if (!x) return null;
  const s = String(x).trim();
  // Accept YYYYMMDD, YYYY-MM-DD
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  return null;
}

type FlexRecord = Record<string, unknown>;

export function normalizeLaw({
  item,
  detail,
}: {
  item: FlexRecord;
  detail: FlexRecord;
}): NormalizedDoc {
  const id =
    item?.id ||
    item?.lawId ||
    item?.법령ID ||
    detail?.id ||
    detail?.lawId ||
    detail?.법령ID;
  if (!id) throw new Error("missing lawId in item/detail");

  const title =
    String(
      item?.title ||
        item?.lawName ||
        item?.법령명 ||
        detail?.title ||
        detail?.lawName ||
        detail?.법령명 ||
        `LAW ${String(id)}`
    );
  const eff = toIsoDate(
    item?.effective_date ||
      item?.effDate ||
      item?.시행일자 ||
      detail?.effective_date ||
      detail?.시행일자
  );

  const body = detail?.body_md || detail?.body || detail?.text || detail?.본문 || "";
  const sourceUrl = String(
    detail?.source_url || detail?.url || item?.url || ""
  ) || null;

  const doc: NormalizedDoc = {
    doc_id: `LAWGO-LAW-${String(id)}`,
    doc_type: "law",
    title,
    jurisdiction: "KR",
    effective_date: eff,
    version: 1, // versioning handled when manifest is updated (effective date change -> bump)
    source_url: sourceUrl,
    body_md: typeof body === "string" ? body : JSON.stringify(body, null, 2),
    meta: {
      provider: "lawgo",
      rawItem: item,
      rawDetailKeys: Object.keys(detail || {}),
    },
  };

  assertNormalizedDoc(doc);
  return doc;
}

export function normalizeCase({
  item,
  detail,
}: {
  item: FlexRecord;
  detail: FlexRecord;
}): NormalizedDoc {
  const id =
    item?.id ||
    item?.caseId ||
    item?.판례ID ||
    detail?.id ||
    detail?.caseId ||
    detail?.판례ID;
  if (!id) throw new Error("missing caseId in item/detail");

  const title = String(
    item?.title ||
      item?.caseName ||
      item?.사건명 ||
      detail?.title ||
      detail?.사건명 ||
      `CASE ${String(id)}`
  );
  const dec = toIsoDate(
    item?.decision_date ||
      item?.decDate ||
      item?.선고일자 ||
      detail?.decision_date ||
      detail?.선고일자 ||
      item?.effective_date
  );

  const body = detail?.body_md || detail?.body || detail?.text || detail?.본문 || "";
  const sourceUrl = String(
    detail?.source_url || detail?.url || item?.url || ""
  ) || null;

  const doc: NormalizedDoc = {
    doc_id: `LAWGO-CASE-${String(id)}`,
    doc_type: "case",
    title,
    jurisdiction: "KR",
    effective_date: dec,
    version: 1,
    source_url: sourceUrl,
    body_md: typeof body === "string" ? body : JSON.stringify(body, null, 2),
    meta: {
      provider: "lawgo",
      rawItem: item,
      rawDetailKeys: Object.keys(detail || {}),
    },
  };

  assertNormalizedDoc(doc);
  return doc;
}
