#!/usr/bin/env node
const pLimit = require("p-limit");
const yargs = require("yargs/yargs");
const { hideBin } = require("yargs/helpers");

const { listCases, fetchCaseDetail } = require("../src/collectors/providers/lawgo_case");
const { normalizeCase } = require("../src/collectors/normalize/lawgo_normalize");
const { loadCheckpoint, saveCheckpoint } = require("../src/collectors/core/checkpoint");
const { writeJson, appendJsonl, writeText } = require("../src/collectors/core/io");

const argv = yargs(hideBin(process.argv))
  .option("pages", { type: "number", default: 1 })
  .option("perPage", { type: "number", default: 20 })
  .option("concurrency", { type: "number", default: 3 })
  .option("out", { type: "string", default: "data/collected/lawgo/case" })
  .parse();

async function main() {
  const log = console;
  const cp = loadCheckpoint("lawgo_case");
  log.log(`[collect:cases] start pages=${argv.pages} perPage=${argv.perPage} concurrency=${argv.concurrency}`);

  const limit = pLimit(argv.concurrency);

  let total = 0;
  for (let page = 1; page <= argv.pages; page++) {
    const items = await listCases({ page, perPage: argv.perPage, log });
    log.log(`[collect:cases] page=${page} items=${items.length}`);

    const tasks = items.map((it) =>
      limit(async () => {
        const caseId = it.id || it.caseId || it.판례ID;
        const detail = await fetchCaseDetail({ caseId, log });
        const doc = normalizeCase({ item: it, detail });

        const base = `${argv.out}/${doc.doc_id}`;
        writeJson(`${base}.json`, doc);
        const mdTitle = `# ${doc.title}\n\n`;
        writeText(`${base}.md`, mdTitle + doc.body_md);

        appendJsonl("data/collected/index.jsonl", {
          collected_at: new Date().toISOString(),
          ...doc,
          path_json: `${base}.json`,
          path_md: `${base}.md`,
        });

        total++;
      })
    );

    await Promise.all(tasks);
  }

  saveCheckpoint("lawgo_case", { ...cp, lastRunAt: new Date().toISOString(), pages: argv.pages, perPage: argv.perPage, total });
  log.log(`[collect:cases] done total=${total}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
