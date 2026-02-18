function parseLawMeta(text) {
  const articles = [];
  const re = /(제\s*\d+\s*조)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (!articles.includes(m[1])) articles.push(m[1]);
    if (articles.length >= 20) break;
  }
  return { articles };
}

function parseCaseMeta(text) {
  // Demo: try find patterns like "사건번호", "선고", etc.
  const caseNo = (text.match(/사건\s*번호\s*[:：]\s*(.+)/i)?.[1] || "").trim();
  const decisionDate = (text.match(/선고\s*일\s*[:：]\s*(.+)/i)?.[1] || "").trim();
  return { caseNo: caseNo || null, decisionDate: decisionDate || null };
}

module.exports = { parseLawMeta, parseCaseMeta };
