"""재현 가능한 투자 리서치 계산: 지표, 전략 백테스트, 포트폴리오 최적화.

모든 신호는 해당 거래일 종가로 계산하고 다음 거래일 수익률에 적용한다.
이는 UI 데모에서도 미래 데이터를 미리 사용하는 오류를 피하기 위한 최소 규칙이다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.quant_pipeline import preprocess
from app.services import ta_utils as ta


def indicators(candles: list[dict]) -> pd.DataFrame:
    df = preprocess(candles)
    close = df["close"].astype(float)
    df["ma5"] = ta.sma(close, 5)
    df["ma20"] = ta.sma(close, 20)
    df["ma60"] = ta.sma(close, 60)
    df["rsi"] = ta.rsi(close, 14, method="ewm")
    macd_line, macd_signal, _ = ta.macd(close, 12, 26, 9)
    df["macd"] = macd_line
    df["macd_signal"] = macd_signal
    bb_upper, _bb_mid, bb_lower = ta.bollinger(close, 20, 2.0)
    df["bb_upper"] = bb_upper
    df["bb_lower"] = bb_lower
    df["volume_ma20"] = df["volume"].astype(float).rolling(20).mean()
    return df


def _position(df: pd.DataFrame, strategy: str) -> pd.Series:
    strategy = strategy.lower()
    if strategy == "rsi":
        enter, exit_ = df["rsi"] < 30, df["rsi"] > 70
    elif strategy == "ma":
        enter = (df["ma5"] > df["ma20"]) & (df["ma5"].shift(1) <= df["ma20"].shift(1))
        exit_ = (df["ma5"] < df["ma20"]) & (df["ma5"].shift(1) >= df["ma20"].shift(1))
    elif strategy == "bollinger":
        enter, exit_ = df["close"] < df["bb_lower"], df["close"] > df["bb_upper"]
    else:  # composite: 추세 + 모멘텀을 동시에 확인
        enter = (df["ma5"] > df["ma20"]) & (df["rsi"] > 50) & (df["macd"] > df["macd_signal"])
        exit_ = (df["ma5"] < df["ma20"]) | (df["rsi"] > 75)
    state = pd.Series(np.nan, index=df.index)
    state.loc[enter] = 1.0
    state.loc[exit_] = 0.0
    return state.ffill().fillna(0.0)


def backtest_strategy(candles: list[dict], strategy: str = "composite", cost_bps: float = 10.0) -> dict:
    """롱온리 일봉 백테스트. 매매비용은 포지션 변동 시 차감한다."""
    df = indicators(candles).dropna()
    if len(df) < 60:
        return {"error": f"데이터 부족: {len(df)}행 (최소 60 필요)"}
    position = _position(df, strategy)
    returns = df["close"].pct_change().fillna(0.0)
    # t일 장 마감 신호는 t+1일 수익률에만 적용
    held = position.shift(1).fillna(0.0)
    turnover = held.diff().abs().fillna(held.abs())
    net = returns * held - turnover * (max(0.0, float(cost_bps)) / 10_000)
    equity = (1 + net).cumprod()
    benchmark = (1 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1
    active = net[held > 0]
    trade_count = int((turnover > 0).sum())
    latest = df.iloc[-1]
    action = "BUY" if bool(position.iloc[-1]) and not bool(position.iloc[-2]) else "SELL" if not bool(position.iloc[-1]) and bool(position.iloc[-2]) else "HOLD"
    return {
        "strategy": strategy,
        "cost_bps": float(cost_bps),
        "total_return_pct": round((equity.iloc[-1] - 1) * 100, 2),
        "buy_hold_return_pct": round((benchmark.iloc[-1] - 1) * 100, 2),
        "sharpe_ratio": round(ta.sharpe_ratio(net), 3),
        "mdd_pct": round(ta.max_drawdown(equity) * 100, 2),
        "trade_count": trade_count,
        "win_rate_pct": round(float((active > 0).mean() * 100) if len(active) else 0.0, 2),
        "latest_signal": action,
        "latest_indicators": {k: round(float(latest[k]), 3) for k in ("ma5", "ma20", "ma60", "rsi", "macd", "macd_signal", "bb_upper", "bb_lower") if pd.notna(latest[k])},
        "times": [x.isoformat() for x in df.index[-252:]],
        "cum_returns": [round(float(x - 1) * 100, 2) for x in equity.iloc[-252:]],
        "bh_returns": [round(float(x - 1) * 100, 2) for x in benchmark.iloc[-252:]],
    }


def screen_pattern(candles: list[dict], model: str) -> dict:
    """선택한 패턴 규칙과 지표로 동일한 방식으로 스크리닝한다."""
    df = indicators(candles).dropna()
    if len(df) < 2:
        return {"error": "지표 계산용 데이터 부족"}
    x, prev = df.iloc[-1], df.iloc[-2]
    model = model.lower()
    if model == "rsi":
        score, reason = (30 - x.rsi) / 10, f"RSI {x.rsi:.1f}"
    elif model == "ma":
        score = 2 if x.ma5 > x.ma20 and prev.ma5 <= prev.ma20 else -2 if x.ma5 < x.ma20 and prev.ma5 >= prev.ma20 else (1 if x.ma5 > x.ma20 else -1)
        reason = f"MA5 {x.ma5:,.0f} / MA20 {x.ma20:,.0f}"
    elif model == "bollinger":
        score = 2 if x.close < x.bb_lower else -2 if x.close > x.bb_upper else 0
        reason = f"종가 {x.close:,.0f}, 밴드 {x.bb_lower:,.0f}~{x.bb_upper:,.0f}"
    else:  # lightgbm 선택 시에도 학습 모델을 가장한 값이 아닌 투명한 앙상블 점수 사용
        score = (1 if x.ma5 > x.ma20 else -1) + (1 if x.macd > x.macd_signal else -1) + (1 if x.rsi < 45 else -1 if x.rsi > 65 else 0)
        reason = f"추세·MACD·RSI 앙상블 (RSI {x.rsi:.1f})"
    signal = "BUY" if score >= 1 else "SELL" if score <= -1 else "HOLD"
    return {"signal": signal, "score": round(float(score), 2), "confidence": min(95, int(55 + abs(score) * 13)), "reason": reason, "rsi": round(float(x.rsi), 2), "price": round(float(x.close), 2)}


def optimize_portfolio(stock_data: list[dict], risk_profile: str) -> dict:
    """최근 일수익률의 공분산을 이용한 long-only 최소분산/수익 혼합 배분."""
    series, labels = [], []
    for item in stock_data:
        df = preprocess(item["candles"])
        s = df["close"].astype(float).pct_change().rename(item["symbol"])
        if s.notna().sum() >= 60:
            series.append(s)
            labels.append(item["symbol"])
    if len(series) < 2:
        return {"error": "최적화에는 유효 종목 2개 이상이 필요합니다."}
    ret = pd.concat(series, axis=1).dropna().tail(252)
    mu = ret.mean().values * 252
    cov = ret.cov().values * 252 + np.eye(len(labels)) * 1e-6
    inv_cov = np.linalg.pinv(cov)
    min_var = inv_cov @ np.ones(len(labels)); min_var /= min_var.sum()
    # 위험 성향에 따라 동일가중과 기대수익 틸트를 점진적으로 확대
    tilt_strength = {"conservative": .10, "moderate": .35, "aggressive": .65}.get(risk_profile, .35)
    mu_score = np.maximum(mu - np.min(mu), 0) + 1e-6; mu_score /= mu_score.sum()
    weights = (1 - tilt_strength) * min_var + tilt_strength * mu_score
    weights = np.clip(weights, 0.05, 0.60); weights /= weights.sum()
    port_ret = float(weights @ mu)
    port_vol = float(np.sqrt(weights @ cov @ weights))
    return {"weights": {label: round(float(w) * 100, 1) for label, w in zip(labels, weights)}, "expected_return_pct": round(port_ret * 100, 2), "expected_volatility_pct": round(port_vol * 100, 2), "method": "최근 252거래일 공분산 기반 long-only 최적화 (비용·세금 미반영)"}
