const fs = require("fs");
const path = require("path");

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function writeJson(fp, obj) {
  ensureDir(path.dirname(fp));
  fs.writeFileSync(fp, JSON.stringify(obj, null, 2), "utf-8");
}

function appendJsonl(fp, obj) {
  ensureDir(path.dirname(fp));
  fs.appendFileSync(fp, JSON.stringify(obj) + "\n", "utf-8");
}

function writeText(fp, text) {
  ensureDir(path.dirname(fp));
  fs.writeFileSync(fp, text, "utf-8");
}

function safeFilename(name) {
  return String(name || "")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);
}

module.exports = { ensureDir, writeJson, appendJsonl, writeText, safeFilename };
