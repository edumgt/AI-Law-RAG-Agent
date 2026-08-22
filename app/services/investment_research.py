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


def ai_predict_return(candles: list[dict]) -> dict | None:
    """피처 엔지니어링 후 시계열 교차검증(TimeSeriesSplit)으로 회귀(수익률) +
    분류(방향성) 신호를 함께 산출한다.

    단일 80/20 분할 대신 여러 폴드의 평균 성능으로 모델을 고르고 confidence를
    매겨서, 한 번의 운 좋은/나쁜 분할에 흔들리지 않게 한다. 종목마다 즉석에서
    가볍게 학습하므로(그리드서치 없음) 유니버스 전체를 스캔해도 응답 지연이 크지
    않다. sklearn 미설치 시 None을 반환하며, 호출측은 과거 샤프비율만으로 순위를
    매기는 방식으로 대체한다.

    confidence(0~1)는 회귀 CV R^2와 분류 정확도/신뢰도를 반반 섞은 대략적인
    품질 지표다 — 캘리브레이션된 확률이 아니라, 호출측이 "이 종목의 AI 예측을
    얼마나 반영할지" 가중치로 쓰기 위한 상대적 지표다.
    """
    try:
        from sklearn.linear_model import Ridge
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import TimeSeriesSplit
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return None

    from app.services.quant_pipeline import feature_engineer, FEATURE_COLS

    df = preprocess(candles)
    df = feature_engineer(df)  # 'target'(방향성 3-class 라벨) 포함
    if len(df) < 80:
        return None

    close = df["close"].astype(float)
    df = df.copy()
    df["fwd_return"] = close.pct_change(5).shift(-5)
    latest_features = df[FEATURE_COLS].iloc[-1:].values
    labeled = df.dropna(subset=["fwd_return"])
    if len(labeled) < 60:
        return None

    X = labeled[FEATURE_COLS].values
    y_reg = labeled["fwd_return"].values

    n_splits = 4 if len(X) >= 150 else 3
    tscv = TimeSeriesSplit(n_splits=n_splits)
    candidates = {
        "Ridge": lambda: Ridge(alpha=1.0),
        "GradientBoosting": lambda: GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.05, random_state=42
        ),
    }
    fold_scores: dict[str, list[float]] = {name: [] for name in candidates}
    for tr_idx, va_idx in tscv.split(X):
        if len(va_idx) < 3:
            continue
        scaler = StandardScaler().fit(X[tr_idx])
        X_tr_s, X_va_s = scaler.transform(X[tr_idx]), scaler.transform(X[va_idx])
        for name, make in candidates.items():
            m = make()
            m.fit(X_tr_s, y_reg[tr_idx])
            fold_scores[name].append(float(m.score(X_va_s, y_reg[va_idx])))

    avg_scores = {name: (float(np.mean(s)) if s else -999.0) for name, s in fold_scores.items()}
    best_name = max(avg_scores, key=avg_scores.get)
    best_r2 = avg_scores[best_name]

    # 최종 예측은 전체 라벨 데이터로 재학습한 best 모델을 사용
    scaler_full = StandardScaler().fit(X)
    final_model = candidates[best_name]()
    final_model.fit(scaler_full.transform(X), y_reg)
    pred_5d = float(final_model.predict(scaler_full.transform(latest_features))[0])

    # 방향성 분류 (LightGBM) — 회귀와 별도로 매수/관망/매도 신호 + 신뢰도 산출
    signal, signal_confidence, cls_acc = 0, 0.5, None
    try:
        import lightgbm as lgb
        y_cls = (labeled["target"].values + 1).astype(int)
        split = max(1, int(len(X) * 0.8))
        if len(X[split:]) >= 5 and len(set(y_cls[split:])) > 1:
            d_tr = lgb.Dataset(X[:split], label=y_cls[:split])
            d_va = lgb.Dataset(X[split:], label=y_cls[split:], reference=d_tr)
            params = {"objective": "multiclass", "num_class": 3, "num_leaves": 15,
                      "learning_rate": 0.08, "feature_fraction": 0.8, "verbosity": -1}
            lgb_model = lgb.train(params, d_tr, num_boost_round=100, valid_sets=[d_va],
                                   callbacks=[lgb.early_stopping(10, verbose=False), lgb.log_evaluation(-1)])
            va_pred = np.argmax(lgb_model.predict(X[split:]), axis=1)
            cls_acc = float((va_pred == y_cls[split:]).mean())
        else:
            lgb_model = lgb.train(
                {"objective": "multiclass", "num_class": 3, "verbosity": -1},
                lgb.Dataset(X, label=y_cls), num_boost_round=50,
            )
        probs = lgb_model.predict(X[-1:])[0]
        signal = int(np.argmax(probs)) - 1
        signal_confidence = float(np.max(probs))
    except Exception:
        signal = 1 if pred_5d > 0 else (-1 if pred_5d < 0 else 0)

    # 5일 예측을 그대로 연환산(252/5 제곱)하면 예측이 조금만 튀어도 지수적으로
    # 폭발해 비현실적인 값이 나온다 (R^2가 음수인 종목에서 특히). 표시용으로 clip.
    pred_5d_clipped = max(-0.2, min(0.2, pred_5d))
    pred_ann = (1 + pred_5d_clipped) ** (252 / 5) - 1

    reg_confidence = max(0.0, min(1.0, (best_r2 + 1) / 2))  # R^2(대략 -1~1)를 0~1로 매핑
    cls_confidence = cls_acc if cls_acc is not None else signal_confidence
    confidence = round(0.5 * reg_confidence + 0.5 * cls_confidence, 4)

    return {
        "pred_5d_return_pct": round(pred_5d * 100, 3),
        "pred_ann_return_pct": round(max(-90.0, min(300.0, pred_ann * 100)), 2),
        "val_r2": round(best_r2, 4),
        "model": f"{best_name}(TimeSeriesSplit {n_splits}-fold)",
        "signal": signal,
        "signal_confidence": round(signal_confidence, 4),
        "confidence": confidence,
    }


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
