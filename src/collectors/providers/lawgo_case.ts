import { createLawgoClient, lawgoGet } from "./lawgo_base";
import type { AxiosResponse } from "axios";

function envKey(): string {
  return process.env.LAWGO_API_KEY || process.env.LAWGO_OC || "";
}

function buildCommonParams(extra: Record<string, unknown> = {}): Record<string, unknown> {
  const key = envKey();
  if (!key) throw new Error("LAWGO_API_KEY (or LAWGO_OC) is required");
  return { OC: key, ...extra };
}

export async function listCases({
  page = 1,
  perPage = 50,
  log = console,
}: {
  page?: number;
  perPage?: number;
  log?: Pick<Console, "warn" | "log">;
}): Promise<unknown[]> {
  const client = createLawgoClient();
  const endpoint = process.env.LAWGO_CASE_LIST_ENDPOINT || "case/list";
  const params = buildCommonParams({ page, perPage, format: "json" });
  const res: AxiosResponse = await lawgoGet(client, endpoint, params, log);

  if (typeof res.data === "string") {
    throw new Error(
      "CASE list returned string (likely XML). Set format=json or implement XML parser."
    );
  }
  const data = res.data as Record<string, unknown>;
  return (data.items || data.results || data.data || []) as unknown[];
}

export async function fetchCaseDetail({
  caseId,
  log = console,
}: {
  caseId: unknown;
  log?: Pick<Console, "warn" | "log">;
}): Promise<Record<string, unknown>> {
  const client = createLawgoClient();
  const endpoint = process.env.LAWGO_CASE_DETAIL_ENDPOINT || "case/detail";
  const params = buildCommonParams({ id: caseId, format: "json" });
  const res: AxiosResponse = await lawgoGet(client, endpoint, params, log);

  if (typeof res.data === "string") {
    throw new Error(
      "CASE detail returned string (likely XML). Implement XML parser or request JSON output."
    );
  }
  return res.data as Record<string, unknown>;
}
