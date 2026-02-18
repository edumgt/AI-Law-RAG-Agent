const crypto = require("crypto");

function sha256(text) {
  return crypto.createHash("sha256").update(String(text || ""), "utf8").digest("hex");
}

module.exports = { sha256 };
