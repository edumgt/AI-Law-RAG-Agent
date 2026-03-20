import { AxiosInstance, AxiosResponse } from "axios";
import { createHttpClient, requestWithRetry } from "../core/http";

/**
 * ⚠️ Provider is designed for 'law.go.kr' open API style, but endpoints vary by plan/approval.
 * Configure via env:
 * - LAWGO_BASE_URL (default: https://open.law.go.kr/LSO/openapi/)
 * - LAWGO_API_KEY  (required)
 * - LAWGO_TIMEOUT_MS (default: 300000)
 */
export function createLawgoClient(): AxiosInstance {
  const baseURL = process.env.LAWGO_BASE_URL || "https://open.law.go.kr/LSO/openapi/";
  const timeoutMs = Number(process.env.LAWGO_TIMEOUT_MS || 300000);
  const client = createHttpClient({ baseURL, timeoutMs });
  return client;
}

export async function lawgoGet(
  client: AxiosInstance,
  url: string,
  params: Record<string, unknown>,
  log: Pick<Console, "warn">
): Promise<AxiosResponse> {
  // Most law.go style APIs use query params like: OC, target, type, etc.
  const res = await requestWithRetry(
    client,
    { method: "GET", url, params },
    { retries: 3, log }
  );
  return res;
}
