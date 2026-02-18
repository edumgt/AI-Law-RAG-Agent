function chunkText(text, { chunkSize = 1200, overlap = 150 } = {}) {
  const cleaned = String(text || "")
    .replace(/\r/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  if (!cleaned) return [];

  // split by double newline first
  const parts = cleaned.split(/\n\n+/);
  const chunks = [];
  let buf = "";

  for (const p of parts) {
    if ((buf + "\n\n" + p).length <= chunkSize) {
      buf = buf ? (buf + "\n\n" + p) : p;
    } else {
      if (buf) chunks.push(buf);
      if (p.length <= chunkSize) {
        buf = p;
      } else {
        // hard split
        let i = 0;
        while (i < p.length) {
          chunks.push(p.slice(i, i + chunkSize));
          i += (chunkSize - overlap);
        }
        buf = "";
      }
    }
  }
  if (buf) chunks.push(buf);

  // add overlap by merging tail/head? (simple)
  return chunks.map((c) => c.trim()).filter(Boolean);
}

module.exports = { chunkText };
