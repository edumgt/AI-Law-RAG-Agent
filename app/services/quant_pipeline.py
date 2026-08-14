"""
퀀트 ML 파이프라인: OHLCV → 전처리 → 피처 → ML/DL → 시그널 → 백테스트 → Alpaca
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any

from app.services import ta_utils as ta

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False


# ── 1. 전처리 ─────────────────────────────────────────────────────────

def preprocess(candles: list[dict]) -> pd.DataFrame:
    """원시 OHLCV → 정제된 DataFrame.

    - Unix timestamp → DatetimeIndex
    - 결측치: forward/backward fill
    - 이상치: 종가 0 이하 제거
    """
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    df = df.ffill().bfill()
    df = df[df["close"] > 0]
    return df


# ── 2. 피처 엔지니어링 ────────────────────────────────────────────────

FEATURE_COLS = [
    "ret_1", "ret_5", "ret_20",
    "ma5_ratio", "ma20_ratio",
    "rsi", "macd", "macd_hist",
    "bb_width", "bb_pos",
    "vol_ratio", "atr",
]


def feature_engineer(df: pd.DataFrame) -> pd.DataFrame:
    """피처 엔지니어링: 수익률, 이동평균, RSI, MACD, 볼린저밴드, 거래량, ATR."""
    out = df.copy()
    c = out["close"].astype(float)
    v = out["volume"].astype(float)

    # 수익률
    out["ret_1"]  = c.pct_change(1)
    out["ret_5"]  = c.pct_change(5)
    out["ret_20"] = c.pct_change(20)

    # 이동평균 비율
    ma5  = c.rolling(5).mean()
    ma20 = c.rolling(20).mean()
    out["ma5_ratio"]  = c / ma5.replace(0, np.nan)
    out["ma20_ratio"] = c / ma20.replace(0, np.nan)

    # RSI (14)
    out["rsi"] = ta.rsi(c, 14)

    # MACD (12/26/9)
    macd_line, _macd_sig, macd_hist = ta.macd(c, 12, 26, 9)
    out["macd"]      = macd_line
    out["macd_hist"] = macd_hist

    # 볼린저밴드 (20, 2σ)
    bb_upper, bb_mid, bb_lower = ta.bollinger(c, 20, 2.0)
    bb_range = (bb_upper - bb_lower).replace(0, np.nan)
    out["bb_width"] = bb_range / bb_mid.replace(0, np.nan)
    out["bb_pos"]   = (c - bb_lower) / bb_range

    # 거래량 비율
    vol_ma20 = v.rolling(20).mean()
    out["vol_ratio"] = v / vol_ma20.replace(0, np.nan)

    # ATR (14)
    out["atr"] = ta.atr(out["high"].astype(float), out["low"].astype(float), c, 14)

    # 타깃: 5일 후 수익률 → 3-class 레이블 (1=매수, 0=관망, -1=매도)
    fut = c.pct_change(5).shift(-5)
    out["target"] = 0
    out.loc[fut >  0.02, "target"] =  1
    out.loc[fut < -0.02, "target"] = -1

    return out.dropna()


# ── 3. LightGBM (ML 방향성 분류) ──────────────────────────────────────

def train_lgb(df: pd.DataFrame) -> tuple[Any, dict]:
    """LightGBM 방향성 분류 모델 (매도/관망/매수 3-class).

    Returns: (model, metrics)
    """
    if not HAS_LGB:
        raise RuntimeError("lightgbm이 설치되지 않았습니다: pip install lightgbm")

    X = df[FEATURE_COLS].values
    y = (df["target"].values + 1).astype(int)   # -1,0,1 → 0,1,2

    split = int(len(X) * 0.8)
    X_tr, X_va = X[:split], X[split:]
    y_tr, y_va = y[:split], y[split:]

    d_tr = lgb.Dataset(X_tr, label=y_tr)
    d_va = lgb.Dataset(X_va, label=y_va, reference=d_tr)

    params = {
        "objective": "multiclass",
        "num_class": 3,
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "verbosity": -1,
        "random_state": 42,
    }
    model = lgb.train(
        params, d_tr,
        num_boost_round=200,
        valid_sets=[d_va],
        callbacks=[lgb.early_stopping(20, verbose=False), lgb.log_evaluation(-1)],
    )

    # 검증 정확도
    preds = np.argmax(model.predict(X_va), axis=1)
    acc = float((preds == y_va).mean())

    # 피처 중요도
    importance = dict(zip(FEATURE_COLS, model.feature_importance("gain").tolist()))

    return model, {"val_accuracy": round(acc, 4), "feature_importance": importance}


def predict_lgb(model: Any, df: pd.DataFrame) -> pd.Series:
    """LightGBM 예측 → 시그널 Series (-1/0/+1)."""
    probs = model.predict(df[FEATURE_COLS].values)   # (N, 3)
    pred = np.argmax(probs, axis=1) - 1              # 0,1,2 → -1,0,+1
    return pd.Series(pred, index=df.index, name="ml_signal")


# ── 4. MLP Neural Net (DL 대안: sklearn MLPClassifier) ───────────────

def train_mlp(df: pd.DataFrame) -> tuple[Any, Any, dict]:
    """MLP 신경망 학습 (64→32→출력).

    sklearn MLPClassifier = 경량 DL 모델 (PyTorch/TF 없이 동작).
    Returns: (model, scaler, metrics)
    """
    if not HAS_SKLEARN:
        raise RuntimeError("scikit-learn이 설치되지 않았습니다: pip install scikit-learn")

    X = df[FEATURE_COLS].values
    y = df["target"].values   # -1, 0, 1

    split = int(len(X) * 0.8)
    X_tr, X_va = X[:split], X[split:]
    y_tr, y_va = y[:split], y[split:]

    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_va_s = scaler.transform(X_va)

    model = MLPClassifier(
        hidden_layer_sizes=(64, 32),
        activation="relu",
        solver="adam",
        learning_rate_init=0.001,
        max_iter=300,
        early_stopping=True,
        validation_fraction=0.1,
        random_state=42,
        verbose=False,
    )
    model.fit(X_tr_s, y_tr)

    acc = float(model.score(X_va_s, y_va))
    return model, scaler, {"val_accuracy": round(acc, 4)}


def predict_mlp(model: Any, scaler: Any, df: pd.DataFrame) -> pd.Series:
    """MLP 예측 → 시그널 Series (-1/0/+1)."""
    X_s = scaler.transform(df[FEATURE_COLS].values)
    pred = model.predict(X_s)
    return pd.Series(pred, index=df.index, name="ml_signal")


# ── 5. 규칙 기반 시그널 (ML 불가 시 fallback) ────────────────────────

def rule_based_signals(df: pd.DataFrame) -> pd.Series:
    """RSI + MACD + 볼린저 점수 합산 → 시그널."""
    score = pd.Series(0.0, index=df.index)

    # RSI
    score += (df["rsi"] < 30).astype(float) * 2
    score -= (df["rsi"] > 70).astype(float) * 2

    # MACD 히스토그램 방향
    score += (df["macd_hist"] > 0).astype(float)
    score -= (df["macd_hist"] < 0).astype(float)

    # 볼린저 위치
    score += (df["bb_pos"] < 0.1).astype(float)
    score -= (df["bb_pos"] > 0.9).astype(float)

    # 이동평균 추세
    score += (df["ma5_ratio"] > df["ma20_ratio"]).astype(float)
    score -= (df["ma5_ratio"] < df["ma20_ratio"]).astype(float)

    sig = pd.Series(0, index=df.index, name="ml_signal")
    sig[score >= 3] = 1
    sig[score <= -3] = -1
    return sig


# ── 6. 백테스트 ───────────────────────────────────────────────────────

def backtest(df: pd.DataFrame, signals: pd.Series) -> dict:
    """
    벡터화 백테스트: 롱 전략 (signal=+1 보유, 그 외 현금).

    Returns: 수익률, 샤프지수, MDD, 승률, 누적수익 시계열
    """
    ret = df["close"].pct_change().fillna(0)
    # 전날 시그널로 오늘 포지션 (룩어헤드 방지)
    pos = signals.shift(1).fillna(0).reindex(ret.index, fill_value=0)

    strat_ret = ret * (pos == 1).astype(float)
    bh_ret    = ret

    cum_strat = (1 + strat_ret).cumprod()
    cum_bh    = (1 + bh_ret).cumprod()

    total_strat = float(cum_strat.iloc[-1] - 1) * 100
    total_bh    = float(cum_bh.iloc[-1] - 1)    * 100

    sharpe = ta.sharpe_ratio(strat_ret)
    mdd    = ta.max_drawdown(cum_strat) * 100

    # 승률 (보유 구간만)
    held_rets = strat_ret[pos == 1]
    win_rate  = float((held_rets > 0).sum() / max(len(held_rets), 1)) * 100

    # 매매 횟수 (포지션 변화)
    trade_count = int((pos.diff().abs() > 0).sum())

    # 최근 252 거래일 시계열
    idx = df.index[-252:]
    times      = [t.isoformat() for t in idx]
    cum_series = [round(float(v) * 100 - 100, 2) for v in cum_strat.reindex(idx).values]
    bh_series  = [round(float(v) * 100 - 100, 2) for v in cum_bh.reindex(idx).values]

    return {
        "total_return_pct":     round(total_strat, 2),
        "buy_hold_return_pct":  round(total_bh, 2),
        "sharpe_ratio":         round(sharpe, 3),
        "mdd_pct":              round(mdd, 2),
        "trade_count":          trade_count,
        "win_rate_pct":         round(win_rate, 2),
        "times":                times,
        "cum_returns":          cum_series,
        "bh_returns":           bh_series,
    }


# ── 7. Alpaca API (Paper Trading Mockup) ─────────────────────────────

async def alpaca_execute(
    symbol: str,
    signal: int,
    quantity: int = 1,
    api_key: str = "",
    secret_key: str = "",
) -> dict:
    """Alpaca Markets Paper Trading 주문 실행.

    실제 연동: ALPACA_API_KEY + ALPACA_SECRET_KEY 환경변수 필요.
    현재는 Mockup (구조만 실제 API 스펙 준수).
    """
    action_map = {1: "buy", -1: "sell", 0: "hold"}
    action = action_map.get(signal, "hold")

    if action == "hold":
        return {"symbol": symbol, "action": "hold", "status": "skipped"}

    # 실제 Alpaca REST 요청 구조 (paper-api.alpaca.markets)
    order_payload = {
        "symbol":        symbol,
        "qty":           str(quantity),
        "side":          action,
        "type":          "market",
        "time_in_force": "day",
    }

    if api_key and secret_key:
        import httpx
        url = "https://paper-api.alpaca.markets/v2/orders"
        headers = {
            "APCA-API-KEY-ID":     api_key,
            "APCA-API-SECRET-KEY": secret_key,
            "Content-Type":        "application/json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(url, json=order_payload, headers=headers)
                resp.raise_for_status()
                return {"symbol": symbol, "action": action, "status": "submitted", "response": resp.json()}
            except Exception as e:
                return {"symbol": symbol, "action": action, "status": "error", "error": str(e)}

    # Mockup 응답 (API 키 없을 때)
    return {
        "symbol":   symbol,
        "action":   action,
        "qty":      quantity,
        "type":     "market",
        "status":   "mockup_submitted",
        "order_id": f"mock-{symbol}-{action}",
        "note":     "실제 실행: ALPACA_API_KEY / ALPACA_SECRET_KEY 환경변수 설정",
    }


# ── 8. 전체 파이프라인 진입점 ─────────────────────────────────────────

async def run_pipeline(
    symbol: str,
    candles: list[dict],
    model_type: str = "lgb",
) -> dict:
    """
    OHLCV → 전처리 → 피처 → ML/DL 학습 → 시그널 → 백테스트 순서로 실행.

    model_type: 'lgb' | 'mlp' | 'rule'
    """
    if len(candles) < 80:
        return {"symbol": symbol, "error": f"데이터 부족: {len(candles)}개 (최소 80개 필요)"}

    # 1) 전처리
    df = preprocess(candles)

    # 2) 피처 엔지니어링
    df = feature_engineer(df)

    if len(df) < 60:
        return {"symbol": symbol, "error": f"피처 계산 후 데이터 부족: {len(df)}행"}

    # 3) 모델 학습 + 예측
    metrics: dict = {}
    if model_type == "lgb" and HAS_LGB:
        model, metrics = train_lgb(df)
        signals = predict_lgb(model, df)
        used_model = "LightGBM"
    elif model_type == "mlp" and HAS_SKLEARN:
        model, scaler, metrics = train_mlp(df)
        signals = predict_mlp(model, scaler, df)
        used_model = "MLP Neural Net"
    else:
        signals = rule_based_signals(df)
        used_model = "Rule-Based (RSI+MACD+BB)"
        metrics = {"note": "ML 라이브러리 미설치 — 규칙 기반 대체"}

    # 4) 백테스트
    bt = backtest(df, signals)

    # 5) 최신 시그널 + Alpaca 주문 (mockup)
    latest_signal  = int(signals.iloc[-1])
    alpaca_result  = await alpaca_execute(symbol, latest_signal)

    # 6) 최근 50 시그널 요약
    recent = signals.iloc[-50:]
    signal_counts = {
        "buy":  int((recent == 1).sum()),
        "hold": int((recent == 0).sum()),
        "sell": int((recent == -1).sum()),
    }

    return {
        "symbol":         symbol,
        "model":          used_model,
        "model_metrics":  metrics,
        "latest_signal":  latest_signal,
        "signal_label":   {1: "매수", 0: "관망", -1: "매도"}.get(latest_signal, "불명"),
        "signal_counts":  signal_counts,
        "backtest":       bt,
        "alpaca":         alpaca_result,
        "data_rows":      len(df),
    }


def backtest_custom_indicator(
    candles: list[dict],
    base: str = "rsi_ma",
    short_window: int = 5,
    mid_window: int = 20,
    rsi_period: int = 14,
    buy_threshold: float = 35.0,
) -> dict:
    """사용자 지정 인디케이터 전략 백테스트.

    base: rsi_ma | macd_bb | volume_rsi | triple_ma
    """
    if len(candles) < 80:
        return {"error": f"데이터 부족: {len(candles)}개 (최소 80개 필요)"}

    short_window = max(2, int(short_window))
    mid_window = max(short_window + 1, int(mid_window))
    rsi_period = max(5, int(rsi_period))
    buy_threshold = float(max(5, min(50, buy_threshold)))
    sell_threshold = float(100 - buy_threshold)

    df = preprocess(candles)
    close = df["close"].astype(float)

    ma_short = ta.sma(close, short_window)
    ma_mid = ta.sma(close, mid_window)
    rsi = ta.rsi(close, rsi_period)

    golden_cross = (ma_short > ma_mid) & (ma_short.shift(1) <= ma_mid.shift(1))
    dead_cross = (ma_short < ma_mid) & (ma_short.shift(1) >= ma_mid.shift(1))
    base = base if base in ("rsi_ma", "macd_bb", "volume_rsi", "triple_ma") else "rsi_ma"
    if base == "macd_bb":
        macd_line, macd_signal, _ = ta.macd(close, 12, 26, 9)
        bb_upper, bb_mid, _bb_lower = ta.bollinger(close, mid_window, 2.0)
        buy_cond = (macd_line > macd_signal) & (macd_line.shift(1) <= macd_signal.shift(1)) & (close < bb_mid)
        sell_cond = (macd_line < macd_signal) & (macd_line.shift(1) >= macd_signal.shift(1)) | (close > bb_upper)
    elif base == "volume_rsi":
        volume_ma = df["volume"].astype(float).rolling(mid_window).mean()
        buy_cond = (rsi < buy_threshold) & (df["volume"] > volume_ma)
        sell_cond = rsi > sell_threshold
    elif base == "triple_ma":
        long_ma = close.rolling(max(mid_window * 2, mid_window + 1)).mean()
        buy_cond = golden_cross & (ma_mid > long_ma)
        sell_cond = dead_cross | (ma_mid < long_ma)
    else:
        buy_cond = golden_cross & (rsi < buy_threshold)
        sell_cond = dead_cross | (rsi > sell_threshold)

    regime = pd.Series(np.nan, index=df.index)
    regime.loc[buy_cond] = 1.0
    regime.loc[sell_cond] = 0.0
    position = regime.ffill().fillna(0.0).rename("ml_signal")

    bt = backtest(df, position)
    return {
        "strategy": {
            "name": f"custom_{base}",
            "base": base,
            "short_window": short_window,
            "mid_window": mid_window,
            "rsi_period": rsi_period,
            "buy_threshold": buy_threshold,
            "sell_threshold": sell_threshold,
        },
        "return_total": round(bt["total_return_pct"] / 100.0, 4),
        "return_buy_hold": round(bt["buy_hold_return_pct"] / 100.0, 4),
        "sharpe": bt["sharpe_ratio"],
        "mdd": round(bt["mdd_pct"] / 100.0, 4),
        "trade_count": bt["trade_count"],
        "win_rate_pct": bt["win_rate_pct"],
        "times": bt["times"],
        "cum_returns": bt["cum_returns"],
        "bh_returns": bt["bh_returns"],
    }
