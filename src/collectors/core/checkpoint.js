const fs = require("fs");
const path = require("path");

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function loadCheckpoint(name, dir = "data/checkpoints") {
  const fp = path.join(process.cwd(), dir, `${name}.json`);
  if (!fs.existsSync(fp)) return { name, createdAt: new Date().toISOString() };
  return JSON.parse(fs.readFileSync(fp, "utf-8"));
}

function saveCheckpoint(name, data, dir = "data/checkpoints") {
  const base = path.join(process.cwd(), dir);
  ensureDir(base);
  const fp = path.join(base, `${name}.json`);
  fs.writeFileSync(fp, JSON.stringify({ ...data, name, updatedAt: new Date().toISOString() }, null, 2), "utf-8");
}

module.exports = { loadCheckpoint, saveCheckpoint };
