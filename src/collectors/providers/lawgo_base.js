const { createHttpClient, requestWithRetry } = require("../core/http");

/**
 * ⚠️ Provider is designed for 'law.go.kr' open API style, but endpoints vary by plan/approval.
 * Configure via env:
 * - LAWGO_BASE_URL (default: https://open.law.go.kr/LSO/openapi/)
 * - LAWGO_API_KEY  (required)
 * - LAWGO_TIMEOUT_MS (default: 300000)
 */
function createLawgoClient() {
  const baseURL = process.env.LAWGO_BASE_URL || "https://open.law.go.kr/LSO/openapi/";
  const timeoutMs = Number(process.env.LAWGO_TIMEOUT_MS || 300000);
  const client = createHttpClient({ baseURL, timeoutMs });
  return client;
}

async function lawgoGet(client, url, params, log) {
  // Most law.go style APIs use query params like: OC, target, type, etc.
  const res = await requestWithRetry(
    client,
    { method: "GET", url, params },
    { retries: 3, log }
  );
  return res;
}

module.exports = { createLawgoClient, lawgoGet };
