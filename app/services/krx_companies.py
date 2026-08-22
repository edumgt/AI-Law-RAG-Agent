"""KRX(한국거래소) 상장법인 전체 목록 기반 종목명 ↔ 종목코드 검색 엔진.

Yahoo Finance의 자동완성 검색(/v1/finance/search)이 일부 한글 검색어에서
"Invalid Search Query" 400을 반환하는 문제가 있어(예: "카카오"), 한글 종목명
검색은 이 로컬 엔진을 우선 사용하고 Yahoo 검색은 보조(해외 종목 등)로만 쓴다.

데이터 출처: KIND(kind.krx.co.kr) 상장법인목록 다운로드 — 코스피/코스닥/코넥스
전체 ~2,800개 종목의 회사명·종목코드·시장구분을 담고 있다. 인증이나 API 키가
필요 없는 공개 다운로드이며, 하루 단위로 캐싱해 재사용한다.

주의: kind.krx.co.kr이 AWS ap-northeast-2 데이터센터 IP 대역을 403으로 막는
것을 실제 운영 서버(EC2)에서 확인했다 — 로컬 개발 환경에서는 정상 접근된다.
그래서 운영에서는 미리 받아 S3(ML_ARTIFACTS_BUCKET의 krx/company_list.json)에
올려둔 걸 우선 읽고, 실패하면(로컬 등) KIND에 직접 접근을 시도한다.
"""
import re

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.services.data_cache import cache_get, cache_set

KIND_URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinAgent/1.0)"}
CACHE_KEY = "krx_company_list"
CACHE_TTL_HOURS = 24
S3_KEY = "krx/company_list.json"

_MARKET_SUFFIX = {
    "유가": "KS",    # KIND 다운로드의 시장구분 표기: 코스피(유가증권시장) = "유가"
    "코스닥": "KQ",
    # 코넥스는 Yahoo Finance에 사실상 데이터가 없어 검색 결과에서 제외한다.
}
_MARKET_LABEL = {"유가": "코스피", "코스닥": "코스닥"}


async def _fetch_krx_list() -> list[dict]:
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        resp = await client.get(KIND_URL)
        resp.raise_for_status()
        html = resp.content.decode("euc-kr", errors="replace")

    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table tr")
    companies = []
    for row in rows[1:]:  # 첫 행은 헤더
        cells = [c.get_text(strip=True) for c in row.select("td")]
        if len(cells) < 3:
            continue
        name, market, code = cells[0], cells[1], cells[2]
        suffix = _MARKET_SUFFIX.get(market)
        if not suffix or not re.fullmatch(r"[0-9A-Z]{6}", code):
            continue
        companies.append({
            "name": name,
            "code": code,
            "market": _MARKET_LABEL.get(market, market),
            "symbol": f"{code}.{suffix}",
        })
    return companies


def _fetch_from_s3() -> list[dict] | None:
    if not settings.ML_ARTIFACTS_BUCKET:
        return None
    try:
        import json
        import boto3
        client = boto3.client("s3", region_name=settings.AWS_REGION)
        obj = client.get_object(Bucket=settings.ML_ARTIFACTS_BUCKET, Key=S3_KEY)
        return json.loads(obj["Body"].read())
    except Exception:
        return None


async def get_krx_companies() -> list[dict]:
    """캐싱된 KRX 상장법인 목록 (없거나 24시간 지났으면 새로 받아온다).

    순서: data_cache(Postgres, 24h) → S3(운영 환경 우선) → KIND 직접 다운로드
    (로컬 개발 등 KIND 접근이 가능한 환경 전용, S3 실패 시 폴백).
    """
    cached = await cache_get(CACHE_KEY, max_age_hours=CACHE_TTL_HOURS)
    if cached:
        return cached

    import asyncio
    companies = await asyncio.to_thread(_fetch_from_s3)

    if not companies:
        try:
            companies = await _fetch_krx_list()
        except Exception:
            return cached or []  # 둘 다 실패 시 있으면 stale 캐시라도, 없으면 빈 리스트

    if companies:
        await cache_set(CACHE_KEY, companies)
    return companies


async def search_companies(query: str, limit: int = 10) -> list[dict]:
    """종목명(부분일치) 또는 종목코드(정확/부분)로 검색.

    Returns: [{"symbol", "name", "exchange", "type"}] — /api/stocks/search와
    동일한 응답 형태라 프론트엔드 수정 없이 그대로 쓸 수 있다.
    """
    q = query.strip()
    if not q:
        return []
    companies = await get_krx_companies()
    if not companies:
        return []

    q_digits = re.fullmatch(r"\d{1,6}", q)
    results = []
    for c in companies:
        matched = (q_digits and c["code"].startswith(q)) or (q in c["name"])
        if matched:
            results.append(c)

    # 종목명이 검색어로 시작하는 것을 우선 정렬 (예: "카카오" 검색 시 "카카오"가
    # "카카오게임즈"보다 먼저 나오게)
    results.sort(key=lambda c: (not c["name"].startswith(q), len(c["name"])))

    return [
        {
            "symbol": c["symbol"],
            "name": c["name"],
            "exchange": c["market"],
            "type": "주식",
        }
        for c in results[:limit]
    ]
