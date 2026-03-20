import { createLawgoClient, lawgoGet } from "./lawgo_base";
import type { AxiosResponse } from "axios";

/**
 * Law collector (API-first).
 * Because API response shapes vary, we support two modes:
 * 1) JSON mode: provider returns { items: [{id,title,effective_date,body_md,source_url,meta}] }
 * 2) XML mode: provider returns raw string, you plug your own parser later.
 *
 * For now we implement a pragmatic JSON-first path and leave hooks for XML.
 *
 * Required env:
 * - LAWGO_API_KEY (or LAWGO_OC depending on your issued key scheme)
 * Optional:
 * - LAWGO_LAW_LIST_ENDPOINT (default: 'law/list')
 * - LAWGO_LAW_DETAIL_ENDPOINT (default: 'law/detail')
 */
function envKey(): string {
  return process.env.LAWGO_API_KEY || process.env.LAWGO_OC || "";
}

function buildCommonParams(extra: Record<string, unknown> = {}): Record<string, unknown> {
  const key = envKey();
  if (!key) throw new Error("LAWGO_API_KEY (or LAWGO_OC) is required");
  return { OC: key, ...extra };
}

export async function listLaws({
  page = 1,
  perPage = 50,
  log = console,
}: {
  page?: number;
  perPage?: number;
  log?: Pick<Console, "warn" | "log">;
}): Promise<unknown[]> {
  const client = createLawgoClient();
  const endpoint = process.env.LAWGO_LAW_LIST_ENDPOINT || "law/list";
  const params = buildCommonParams({ page, perPage, format: "json" });
  const res: AxiosResponse = await lawgoGet(client, endpoint, params, log);

  // Expecting JSON: { items: [...] } or { results: [...] }
  if (typeof res.data === "string") {
    throw new Error(
      "LAW list returned string (likely XML). Set format=json or implement XML parser."
    );
  }
  const data = res.data as Record<string, unknown>;
  return (data.items || data.results || data.data || []) as unknown[];
}

export async function fetchLawDetail({
  lawId,
  log = console,
}: {
  lawId: unknown;
  log?: Pick<Console, "warn" | "log">;
}): Promise<Record<string, unknown>> {
  const client = createLawgoClient();
  const endpoint = process.env.LAWGO_LAW_DETAIL_ENDPOINT || "law/detail";
  const params = buildCommonParams({ id: lawId, format: "json" });
  const res: AxiosResponse = await lawgoGet(client, endpoint, params, log);

  if (typeof res.data === "string") {
    throw new Error(
      "LAW detail returned string (likely XML). Implement XML parser or request JSON output."
    );
  }
  return res.data as Record<string, unknown>;
}
