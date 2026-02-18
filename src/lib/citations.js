function buildCitations(docs) {
  const lines = [];
  for (let i = 0; i < docs.length; i++) {
    const d = docs[i];
    const vid = d.docId ? `${d.docId}@v${d.docVersion || 1}` : "DOC";
    const eff = d.effectiveDate ? `, 기준일 ${d.effectiveDate}` : "";
    const head = `[C${i + 1}] ${vid} — ${d.title || ""} (${d.docType}, score ${d.score.toFixed(3)}${eff})\nsource: ${d.source}`;
    const snippet = d.text.length > 600 ? d.text.slice(0, 600) + "..." : d.text;
    lines.push(head);
    lines.push(snippet);
    lines.push("");
  }
  return lines.join("\n");
}

module.exports = { buildCitations };
