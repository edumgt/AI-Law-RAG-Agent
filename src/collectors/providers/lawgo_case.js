const { createLawgoClient, lawgoGet } = require("./lawgo_base");

function envKey() {
  return process.env.LAWGO_API_KEY || process.env.LAWGO_OC || "";
}

function buildCommonParams(extra = {}) {
  const key = envKey();
  if (!key) throw new Error("LAWGO_API_KEY (or LAWGO_OC) is required");
  return { OC: key, ...extra };
}

async function listCases({ page = 1, perPage = 50, log = console }) {
  const client = createLawgoClient();
  const endpoint = process.env.LAWGO_CASE_LIST_ENDPOINT || "case/list";
  const params = buildCommonParams({ page, perPage, format: "json" });
  const res = await lawgoGet(client, endpoint, params, log);

  if (typeof res.data === "string") {
    throw new Error("CASE list returned string (likely XML). Set format=json or implement XML parser.");
  }
  const items = res.data.items || res.data.results || res.data.data || [];
  return items;
}

async function fetchCaseDetail({ caseId, log = console }) {
  const client = createLawgoClient();
  const endpoint = process.env.LAWGO_CASE_DETAIL_ENDPOINT || "case/detail";
  const params = buildCommonParams({ id: caseId, format: "json" });
  const res = await lawgoGet(client, endpoint, params, log);

  if (typeof res.data === "string") {
    throw new Error("CASE detail returned string (likely XML). Implement XML parser or request JSON output.");
  }
  return res.data;
}

module.exports = { listCases, fetchCaseDetail };
