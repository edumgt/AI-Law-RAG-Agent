"""주가 데이터 서비스: Yahoo Finance API 기반."""
import time
import httpx
from datetime import datetime, timezone
from typing import Any

from app.services.data_cache import cache_get, cache_set

YAHOO_CHART = "https://query2.finance.yahoo.com/v8/finance/chart"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinAgent/1.0)"}

# 국내 상장사 퀀트 스크리닝 대상 유니버스 (섹터 분산 ~30종목).
# 실제 추천/자동매매/스크리닝은 이 유니버스 전체를 스캔해 데이터 기반으로 종목을 선정한다 —
# 화면에 노출되는 개별 종목은 매 요청마다 계산된 스코어에 따라 달라질 수 있다.
QUANT_STOCKS = [
    {"symbol": "005930.KS", "name": "삼성전자", "sector": "IT/반도체"},
    {"symbol": "000660.KS", "name": "SK하이닉스", "sector": "IT/반도체"},
    {"symbol": "042700.KS", "name": "한미반도체", "sector": "IT/반도체"},
    {"symbol": "009150.KS", "name": "삼성전기", "sector": "전자부품"},
    {"symbol": "035420.KS", "name": "NAVER", "sector": "IT/인터넷"},
    {"symbol": "035720.KS", "name": "카카오", "sector": "IT/인터넷"},
    {"symbol": "018260.KS", "name": "삼성에스디에스", "sector": "IT서비스"},
    {"symbol": "259960.KS", "name": "크래프톤", "sector": "게임"},
    {"symbol": "036570.KS", "name": "엔씨소프트", "sector": "게임"},
    {"symbol": "251270.KS", "name": "넷마블", "sector": "게임"},
    {"symbol": "005380.KS", "name": "현대자동차", "sector": "자동차"},
    {"symbol": "000270.KS", "name": "기아", "sector": "자동차"},
    {"symbol": "051910.KS", "name": "LG화학", "sector": "화학/배터리"},
    {"symbol": "006400.KS", "name": "삼성SDI", "sector": "화학/배터리"},
    {"symbol": "373220.KS", "name": "LG에너지솔루션", "sector": "화학/배터리"},
    {"symbol": "010950.KS", "name": "S-Oil", "sector": "정유"},
    {"symbol": "207940.KS", "name": "삼성바이오로직스", "sector": "바이오"},
    {"symbol": "068270.KS", "name": "셀트리온", "sector": "바이오"},
    {"symbol": "105560.KS", "name": "KB금융", "sector": "금융"},
    {"symbol": "055550.KS", "name": "신한지주", "sector": "금융"},
    {"symbol": "086790.KS", "name": "하나금융지주", "sector": "금융"},
    {"symbol": "005490.KS", "name": "POSCO홀딩스", "sector": "철강"},
    {"symbol": "010130.KS", "name": "고려아연", "sector": "비철금속"},
    {"symbol": "034730.KS", "name": "SK", "sector": "지주"},
    {"symbol": "003550.KS", "name": "LG", "sector": "지주"},
    {"symbol": "015760.KS", "name": "한국전력", "sector": "유틸리티"},
    {"symbol": "017670.KS", "name": "SK텔레콤", "sector": "통신"},
    {"symbol": "030200.KS", "name": "KT", "sector": "통신"},
    {"symbol": "097950.KS", "name": "CJ제일제당", "sector": "식품"},
    {"symbol": "090430.KS", "name": "아모레퍼시픽", "sector": "화장품"},
    {"symbol": "352820.KS", "name": "하이브", "sector": "엔터테인먼트"},
]

MARKET_INDICES = [
    {"symbol": "^KS11", "name": "KOSPI"},
    {"symbol": "^KQ11", "name": "KOSDAQ"},
    {"symbol": "KRW=X", "name": "USD/KRW"},
]


async def _yahoo_chart(symbol: str, interval: str, range_: str) -> dict | None:
    url = f"{YAHOO_CHART}/{symbol}"
    params = {"interval": interval, "range": range_}
    async with httpx.AsyncClient(timeout=15.0, headers=HEADERS) as client:
        try:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("chart", {}).get("result", [])
            return result[0] if result else None
        except Exception:
            return None


async def get_quote(symbol: str) -> dict:
    """현재 주가 정보."""
    data = await _yahoo_chart(symbol, "1d", "1d")
    if not data:
        return {"symbol": symbol, "error": "데이터 없음"}

    meta = data.get("meta", {})
    return {
        "symbol": symbol,
        "name": meta.get("longName") or meta.get("shortName") or symbol,
        "price": meta.get("regularMarketPrice"),
        "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose"),
        "change": None,
        "change_pct": None,
        "currency": meta.get("currency", "KRW"),
        "market": meta.get("exchangeName"),
    }


_yahoo_session: dict = {"cookies": None, "crumb": None, "ts": 0.0}
_CRUMB_TTL_SEC = 1800


async def _get_yahoo_crumb() -> tuple[dict, str] | None:
    """quoteSummary(v10)는 crumb+쿠키가 있어야 401을 피할 수 있다.
    fc.yahoo.com에서 쿠키를 받고 getcrumb으로 crumb을 발급받는 흐름을 30분 캐싱한다.
    """
    now = time.time()
    if _yahoo_session["crumb"] and now - _yahoo_session["ts"] < _CRUMB_TTL_SEC:
        return _yahoo_session["cookies"], _yahoo_session["crumb"]
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=HEADERS) as client:
            await client.get("https://fc.yahoo.com")
            resp = await client.get(
                "https://query2.finance.yahoo.com/v1/test/getcrumb", cookies=client.cookies,
            )
            crumb = resp.text.strip()
            cookies = dict(client.cookies)
        if not crumb or "Invalid" in crumb or "<html" in crumb.lower():
            return None
        _yahoo_session.update({"cookies": cookies, "crumb": crumb, "ts": now})
        return cookies, crumb
    except Exception:
        return None


def _raw(mod: dict | None, key: str) -> Any:
    """Yahoo quoteSummary 필드는 대부분 {"raw": ..., "fmt": ...} 형태."""
    if not mod:
        return None
    v = mod.get(key)
    if isinstance(v, dict):
        return v.get("raw")
    return v


async def get_fundamentals(symbol: str) -> dict:
    """Yahoo Finance quoteSummary 기반 실제 기업 펀더멘털 (PER/PBR/ROE/분기실적 등).

    일부 필드(특히 재무상태표 총자산/부채 상세)는 Yahoo가 국내 상장사에 대해
    제공하지 않는 경우가 있어 해당 값은 null로 반환한다 — 프론트엔드가 '데이터 없음'
    으로 표시하며, 값을 지어내지 않는다.
    """
    cache_key = f"fundamentals:{symbol}"
    cached = await cache_get(cache_key, max_age_hours=6)
    if cached is not None:
        return cached

    session = await _get_yahoo_crumb()
    modules = "price,summaryDetail,defaultKeyStatistics,financialData,incomeStatementHistoryQuarterly,balanceSheetHistory"
    params: dict[str, Any] = {"modules": modules}
    cookies = None
    if session:
        cookies, crumb = session
        params["crumb"] = crumb

    try:
        async with httpx.AsyncClient(timeout=12.0, headers=HEADERS, cookies=cookies) as client:
            resp = await client.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}", params=params,
            )
            resp.raise_for_status()
            data = resp.json()
        result = data.get("quoteSummary", {}).get("result")
        if not result:
            return {"symbol": symbol, "error": "데이터 없음"}
        r = result[0]
    except Exception as e:
        return {"symbol": symbol, "error": f"조회 실패: {e}"}

    price_mod = r.get("price", {})
    summary = r.get("summaryDetail", {})
    stats = r.get("defaultKeyStatistics", {})
    fin = r.get("financialData", {})

    def _pct(mod: dict, key: str) -> float | None:
        v = _raw(mod, key)
        return round(v * 100, 2) if v is not None else None

    def _eok(v: float | None) -> float | None:
        """원 단위 -> 억원 단위 (기존 목업과 동일한 스케일)."""
        return round(v / 1e8, 0) if v is not None else None

    quarters, revenue, op, net = [], [], [], []
    inc_history = list(reversed(r.get("incomeStatementHistoryQuarterly", {}).get("incomeStatementHistory", [])))
    for q in inc_history:
        end = q.get("endDate", {}).get("fmt", "")
        quarters.append(f"{end[2:4]}Q{(int(end[5:7]) - 1) // 3 + 1}" if end else "")
        revenue.append(_eok(_raw(q, "totalRevenue")))
        op.append(_eok(_raw(q, "operatingIncome")))
        net.append(_eok(_raw(q, "netIncome")))

    bs_list = r.get("balanceSheetHistory", {}).get("balanceSheetStatements", [])
    bs = bs_list[0] if bs_list else {}

    fundamentals = {
        "symbol": symbol,
        "name": price_mod.get("longName") or price_mod.get("shortName") or symbol,
        "price": _raw(price_mod, "regularMarketPrice"),
        "chg": _pct(price_mod, "regularMarketChangePercent"),
        "cap": _eok(_raw(price_mod, "marketCap") or _raw(summary, "marketCap")),
        "per": _raw(summary, "trailingPE") or _raw(stats, "forwardPE"),
        "pbr": _raw(stats, "priceToBook"),
        "eps": _raw(stats, "trailingEps"),
        "bps": _raw(stats, "bookValue"),
        "roe": _pct(fin, "returnOnEquity"),
        "roa": _pct(fin, "returnOnAssets"),
        "debt": round(_raw(fin, "debtToEquity"), 1) if _raw(fin, "debtToEquity") is not None else None,
        "div": _raw(summary, "dividendRate"),
        "divYield": _pct(summary, "dividendYield"),
        "opMargin": _pct(fin, "operatingMargins"),
        "revenue": revenue,
        "op": op,
        "net": net,
        "quarters": quarters,
        "assets": _eok(_raw(bs, "totalAssets")),
        "equity": _eok(_raw(bs, "totalStockholderEquity")),
        "liabilities": _eok(_raw(bs, "totalLiab")),
        "cash": _eok(_raw(bs, "cash")),
    }
    await cache_set(cache_key, fundamentals)
    return fundamentals


async def get_candles(symbol: str, period: str = "1y", interval: str = "1d") -> dict:
    """캔들 차트 데이터 (OHLCV). 반복 스캔 시 Yahoo 호출을 줄이기 위해 캐시를 우선 사용한다."""
    cache_key = f"candles:{symbol}:{period}:{interval}"
    cached = await cache_get(cache_key, max_age_hours=6)
    if cached is not None:
        return cached

    # 10년치는 10y range로 요청
    data = await _yahoo_chart(symbol, interval, period)
    if not data:
        return {"symbol": symbol, "candles": []}

    timestamps = data.get("timestamp", [])
    indicators = data.get("indicators", {}).get("quote", [{}])[0]
    opens = indicators.get("open", [])
    highs = indicators.get("high", [])
    lows = indicators.get("low", [])
    closes = indicators.get("close", [])
    volumes = indicators.get("volume", [])

    candles = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        candles.append({
            "time": ts,
            "open": opens[i] if i < len(opens) else None,
            "high": highs[i] if i < len(highs) else None,
            "low": lows[i] if i < len(lows) else None,
            "close": closes[i],
            "volume": volumes[i] if i < len(volumes) else None,
        })

    result = {"symbol": symbol, "interval": interval, "period": period, "candles": candles}
    if candles:
        await cache_set(cache_key, result)
    return result


async def get_market_summary() -> list[dict]:
    """시장 지수 요약."""
    results = []
    for idx in MARKET_INDICES:
        q = await get_quote(idx["symbol"])
        prev = q.get("prev_close")
        price = q.get("price")
        change_pct = None
        if prev and price and prev != 0:
            change_pct = round((price - prev) / prev * 100, 2)
        results.append({
            "symbol": idx["symbol"],
            "name": idx["name"],
            "price": price,
            "change_pct": change_pct,
        })
    return results


# ── 기술적 지표 계산 ──────────────────────────────────────────────────
def _calc_rsi(closes: list[float], period: int = 14) -> list[float | None]:
    rsi = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi
    gains, losses = [], []
    for i in range(1, period + 1):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    for i in range(period, len(closes)):
        if i > period:
            diff = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(diff, 0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-diff, 0)) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        rsi[i] = round(100 - (100 / (1 + rs)), 2)
    return rsi


def _calc_sma(closes: list[float], period: int) -> list[float | None]:
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = round(sum(closes[i - period + 1:i + 1]) / period, 2)
    return result


def _calc_bollinger(closes: list[float], period: int = 20, std_mult: float = 2.0):
    upper, lower, mid = [None] * len(closes), [None] * len(closes), [None] * len(closes)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1:i + 1]
        m = sum(window) / period
        std = (sum((x - m) ** 2 for x in window) / period) ** 0.5
        mid[i] = round(m, 2)
        upper[i] = round(m + std_mult * std, 2)
        lower[i] = round(m - std_mult * std, 2)
    return upper, mid, lower


async def get_quant_indicators(symbol: str, period: str = "2y") -> dict:
    """기술적 지표 + AI 매매 시그널."""
    data = await get_candles(symbol, period=period)
    candles = data.get("candles", [])
    if len(candles) < 20:
        return {"symbol": symbol, "error": "데이터 부족"}

    closes = [c["close"] for c in candles if c["close"] is not None]
    times = [c["time"] for c in candles if c["close"] is not None]

    rsi = _calc_rsi(closes)
    ma5 = _calc_sma(closes, 5)
    ma20 = _calc_sma(closes, 20)
    ma60 = _calc_sma(closes, 60)
    bb_upper, bb_mid, bb_lower = _calc_bollinger(closes)

    # 매매 시그널 (규칙 기반 + AI 해석)
    signal = _generate_signal(closes, rsi, ma5, ma20, ma60, bb_upper, bb_lower)

    return {
        "symbol": symbol,
        "times": times[-100:],
        "closes": closes[-100:],
        "rsi": rsi[-100:],
        "ma5": ma5[-100:],
        "ma20": ma20[-100:],
        "ma60": ma60[-100:],
        "bb_upper": bb_upper[-100:],
        "bb_mid": bb_mid[-100:],
        "bb_lower": bb_lower[-100:],
        "signal": signal,
        "current_price": closes[-1],
        "current_rsi": rsi[-1],
    }


def _generate_signal(closes, rsi, ma5, ma20, ma60, bb_upper, bb_lower) -> dict:
    """규칙 기반 매매 시그널 생성."""
    n = len(closes) - 1
    signals = []
    score = 0  # + = 매수, - = 매도

    # RSI 시그널
    if rsi[n] is not None:
        if rsi[n] < 30:
            signals.append("RSI 과매도 (매수 신호)")
            score += 2
        elif rsi[n] > 70:
            signals.append("RSI 과매수 (매도 신호)")
            score -= 2
        else:
            signals.append(f"RSI 중립 ({rsi[n]:.1f})")

    # 이동평균 골든/데드크로스
    if ma5[n] and ma20[n] and ma5[n-1] and ma20[n-1]:
        if ma5[n] > ma20[n] and ma5[n-1] <= ma20[n-1]:
            signals.append("골든크로스 (강력 매수)")
            score += 3
        elif ma5[n] < ma20[n] and ma5[n-1] >= ma20[n-1]:
            signals.append("데드크로스 (강력 매도)")
            score -= 3
        elif ma5[n] > ma20[n]:
            signals.append("단기 이평 > 중기 이평 (매수 우위)")
            score += 1
        else:
            signals.append("단기 이평 < 중기 이평 (매도 우위)")
            score -= 1

    # 볼린저밴드
    if bb_upper[n] and bb_lower[n]:
        if closes[n] < bb_lower[n]:
            signals.append("볼린저 하단 이탈 (반등 가능)")
            score += 1
        elif closes[n] > bb_upper[n]:
            signals.append("볼린저 상단 돌파 (조정 가능)")
            score -= 1

    # 최종 판단
    if score >= 3:
        action, color = "강력 매수", "green"
    elif score >= 1:
        action, color = "매수", "lightgreen"
    elif score <= -3:
        action, color = "강력 매도", "red"
    elif score <= -1:
        action, color = "매도", "salmon"
    else:
        action, color = "관망", "gray"

    return {"action": action, "color": color, "score": score, "reasons": signals}
