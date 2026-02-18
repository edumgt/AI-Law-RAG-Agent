const fs = require("fs");
const path = require("path");

function loadManifest(manifestPath = "data/manifest.json") {
  const abs = path.isAbsolute(manifestPath) ? manifestPath : path.join(process.cwd(), manifestPath);
  if (!fs.existsSync(abs)) return null;
  const raw = fs.readFileSync(abs, "utf-8");
  return JSON.parse(raw);
}

module.exports = { loadManifest };
