function applyGuardrails(question) {
  const q = String(question || "").toLowerCase();

  // very small demo policy set
  const banned = [
    "증거 조작",
    "증거를 조작",
    "위조",
    "협박",
    "불법",
    "사기치는 법",
    "탈세",
    "몰래 녹음",
    "스토킹",
    "해킹",
  ];

  for (const b of banned) {
    if (q.includes(b.toLowerCase())) {
      return {
        blocked: true,
        response:
`요청하신 내용은 타인의 권리 침해 또는 불법행위를 조장할 수 있어 도와드릴 수 없습니다.

대신, 합법적인 범위에서 가능한 대응(예: 신고/상담 절차, 증거 보존의 합법적 방법, 분쟁 예방 체크리스트)은 안내해드릴 수 있어요.
원하시면 상황을 합법 범위에서 다시 설명해 주세요.`,
      };
    }
  }

  return { blocked: false };
}

module.exports = { applyGuardrails };
