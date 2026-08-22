"""SageMaker 배치 학습 진입점.

퀀트 스크리닝 유니버스(app/services/stock.py의 QUANT_STOCKS와 동일한 심볼)
전 종목에 대해 매일 1회:
  1) LightGBM으로 5거래일 방향성(매수/관망/매도) 분류 모델을 재학습하고
  2) Ridge 회귀로 5거래일 수익률을 재학습해
결과를 scores.json으로 저장한다. 이 파일은 앱의 robo_allocation 엔드포인트가
S3에서 읽어 실시간 스코어링에 보조 시그널로 섞어 쓴다
(app/services/quant_ai_scores.py 참고). 배치 결과가 없어도 실시간 계산만으로
동작하므로 이 잡이 실패해도 서비스에는 영향이 없다.

SageMaker 사전빌드 scikit-learn 프레임워크 컨테이너의 script-mode로 실행되며
SM_MODEL_DIR / SM_OUTPUT_DATA_DIR 표준 환경변수를 사용한다. 별도 S3 입력 채널
없이 컨테이너가 인터넷에 직접 접근해(VpcConfig 미설정) Yahoo Finance에서
데이터를 가져온다.

독립 실행 컨테이너이므로 앱 패키지(app.*)에 의존하지 않고 필요한 로직만 복제한다.
QUANT_STOCKS 유니버스를 바꾸면 이 파일의 UNIVERSE도 함께 갱신해야 한다.

주의: SageMaker sklearn 빌트인 컨테이너(1.2-1)는 Python 3.9라 `dict | None` 같은
PEP 604 유니온 문법이 런타임에 TypeError를 낸다 — 아래 __future__ import로 회피.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.request

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

YAHOO_CHART = "https://query2.finance.yahoo.com/v8/finance/chart"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinAgent/1.0)"}

# app/services/stock.py QUANT_STOCKS와 동일하게 유지할 것
UNIVERSE = [
    "005930.KS", "000660.KS", "042700.KS", "009150.KS", "035420.KS",
    "035720.KS", "018260.KS", "259960.KS", "036570.KS", "251270.KS",
    "005380.KS", "000270.KS", "051910.KS", "006400.KS", "373220.KS",
    "010950.KS", "207940.KS", "068270.KS", "105560.KS", "055550.KS",
    "086790.KS", "005490.KS", "010130.KS", "034730.KS", "003550.KS",
    "015760.KS", "017670.KS", "030200.KS", "097950.KS", "090430.KS",
    "352820.KS",
]

FEATURE_COLS = [
    "ret_1", "ret_5", "ret_20", "ma5_ratio", "ma20_ratio",
    "rsi", "macd", "macd_hist", "bb_width", "bb_pos", "vol_ratio", "atr",
]


def fetch_candles(symbol: str, period: str = "2y", interval: str = "1d") -> list[dict]:
    url = f"{YAHOO_CHART}/{symbol}?interval={interval}&range={period}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    result = data.get("chart", {}).get("result") or []
    if not result:
        return []
    r = result[0]
    ts = r.get("timestamp", [])
    q = r.get("indicators", {}).get("quote", [{}])[0]
    closes = q.get("close", [])
    candles = []
    for i, t in enumerate(ts):
        if i < len(closes) and closes[i] is not None:
            candles.append({
                "time": t,
                "open": q.get("open", [None] * len(ts))[i],
                "high": q.get("high", [None] * len(ts))[i],
                "low": q.get("low", [None] * len(ts))[i],
                "close": closes[i],
                "volume": q.get("volume", [None] * len(ts))[i],
            })
    return candles


def build_features(candles: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.set_index("time").sort_index()
    df = df[["open", "high", "low", "close", "volume"]].apply(pd.to_numeric, errors="coerce")
    df = df.ffill().bfill()
    df = df[df["close"] > 0]

    c = df["close"]
    df["ret_1"] = c.pct_change(1)
    df["ret_5"] = c.pct_change(5)
    df["ret_20"] = c.pct_change(20)

    ma5, ma20 = c.rolling(5).mean(), c.rolling(20).mean()
    df["ma5_ratio"] = c / ma5.replace(0, np.nan)
    df["ma20_ratio"] = c / ma20.replace(0, np.nan)

    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi"] = 100 - (100 / (1 + rs))

    ema12, ema26 = c.ewm(span=12).mean(), c.ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_hist"] = df["macd"] - df["macd"].ewm(span=9).mean()

    std20 = c.rolling(20).std()
    bb_range = (4 * std20).replace(0, np.nan)
    df["bb_width"] = bb_range / ma20.replace(0, np.nan)
    df["bb_pos"] = (c - (ma20 - 2 * std20)) / bb_range

    vol_ma20 = df["volume"].rolling(20).mean()
    df["vol_ratio"] = df["volume"] / vol_ma20.replace(0, np.nan)

    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - c.shift()).abs(),
        (df["low"] - c.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.rolling(14).mean()

    df["fwd_return"] = c.pct_change(5).shift(-5)
    df["target"] = 0
    df.loc[df["fwd_return"] > 0.02, "target"] = 1
    df.loc[df["fwd_return"] < -0.02, "target"] = -1
    return df.dropna()


def train_symbol(symbol: str) -> dict | None:
    """TimeSeriesSplit 교차검증으로 회귀(수익률) + 분류(방향성)를 함께 학습한다.

    단일 80/20 분할 대신 여러 폴드의 평균 성능(및 그 성능으로 고른 최종 모델)을
    쓰고, confidence(0~1, 회귀 CV R^2 + 분류 정확도/신뢰도를 반반 섞은 대략적인
    품질 지표)를 함께 내보낸다. app/services/ml.py의 robo_allocation이 이 값으로
    종목별 AI 신호의 반영 비중을 조절한다 (app/services/investment_research.py의
    ai_predict_return과 동일한 방식 — 필드명을 맞춰서 실시간/배치 결과를 동일하게 다룸).
    """
    candles = fetch_candles(symbol)
    if len(candles) < 120:
        return None
    df = build_features(candles)
    if len(df) < 80:
        return None

    X = df[FEATURE_COLS].values
    y_cls = (df["target"].values + 1).astype(int)
    y_reg = df["fwd_return"].values

    result: dict = {"rows": len(df)}

    # ── 방향성 분류 (LightGBM) ────────────────────────────────────────
    signal, signal_confidence, cls_acc = 0, 0.5, None
    cls_split = int(len(X) * 0.8)
    if lgb is not None and len(X[cls_split:]) >= 5 and len(set(y_cls[cls_split:])) > 1:
        d_tr = lgb.Dataset(X[:cls_split], label=y_cls[:cls_split])
        d_va = lgb.Dataset(X[cls_split:], label=y_cls[cls_split:], reference=d_tr)
        params = {
            "objective": "multiclass", "num_class": 3, "num_leaves": 31,
            "learning_rate": 0.05, "feature_fraction": 0.8, "verbosity": -1,
        }
        model = lgb.train(
            params, d_tr, num_boost_round=150, valid_sets=[d_va],
            callbacks=[lgb.early_stopping(15, verbose=False), lgb.log_evaluation(-1)],
        )
        pred = np.argmax(model.predict(X[cls_split:]), axis=1)
        cls_acc = float((pred == y_cls[cls_split:]).mean())
        result["cls_val_accuracy"] = round(cls_acc, 4)
        latest_probs = model.predict(X[-1:])[0]
        signal = int(np.argmax(latest_probs)) - 1
        signal_confidence = float(np.max(latest_probs))

    # ── 수익률 회귀: TimeSeriesSplit으로 Ridge/GradientBoosting 중 더 나은 쪽 선택 ──
    n_splits = 4 if len(X) >= 150 else 3
    tscv = TimeSeriesSplit(n_splits=n_splits)
    reg_candidates = {
        "Ridge": lambda: Ridge(alpha=1.0),
        "GradientBoosting": lambda: GradientBoostingRegressor(
            n_estimators=80, max_depth=3, learning_rate=0.05, random_state=42
        ),
    }
    fold_scores: dict[str, list[float]] = {name: [] for name in reg_candidates}
    for tr_idx, va_idx in tscv.split(X):
        if len(va_idx) < 3:
            continue
        scaler = StandardScaler().fit(X[tr_idx])
        X_tr_s, X_va_s = scaler.transform(X[tr_idx]), scaler.transform(X[va_idx])
        for name, make in reg_candidates.items():
            m = make()
            m.fit(X_tr_s, y_reg[tr_idx])
            fold_scores[name].append(float(m.score(X_va_s, y_reg[va_idx])))

    avg_scores = {name: (float(np.mean(s)) if s else -999.0) for name, s in fold_scores.items()}
    best_name = max(avg_scores, key=avg_scores.get)
    best_r2 = avg_scores[best_name]
    result["reg_val_r2"] = round(best_r2, 4)

    scaler_full = StandardScaler().fit(X)
    final_model = reg_candidates[best_name]()
    final_model.fit(scaler_full.transform(X), y_reg)
    pred_5d = float(final_model.predict(scaler_full.transform(X[-1:]))[0])

    # 5일 수익률을 그대로 연환산(252/5 제곱)하면 예측이 조금만 튀어도(R^2가 음수인
    # 종목이 흔함) 지수적으로 폭발해 수백만 % 같은 비현실적 값이 나온다. 표시용으로
    # 5일 예측값과 최종 연환산 값을 각각 clip한다.
    pred_5d_clipped = max(-0.2, min(0.2, pred_5d))
    ann_return = (1 + pred_5d_clipped) ** (252 / 5) - 1

    reg_confidence = max(0.0, min(1.0, (best_r2 + 1) / 2))  # R^2(대략 -1~1)를 0~1로 매핑
    cls_confidence = cls_acc if cls_acc is not None else signal_confidence
    confidence = round(0.5 * reg_confidence + 0.5 * cls_confidence, 4)

    result["pred_5d_return_pct"] = round(pred_5d * 100, 3)
    result["pred_ann_return_pct"] = round(max(-90.0, min(300.0, ann_return * 100)), 2)
    result["model"] = f"{best_name}(TimeSeriesSplit {n_splits}-fold)"
    result["latest_signal"] = signal
    result["latest_signal_confidence"] = round(signal_confidence, 4)
    result["confidence"] = confidence
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=str, default=",".join(UNIVERSE))
    args = parser.parse_args()

    model_dir = os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
    output_dir = os.environ.get("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    symbols = [s.strip() for s in args.universe.split(",") if s.strip()]
    scores: dict[str, dict] = {}
    failures: list[str] = []

    for sym in symbols:
        try:
            r = train_symbol(sym)
            if r:
                scores[sym] = r
            else:
                failures.append(f"{sym}: 데이터 부족")
        except Exception as e:  # 종목 하나 실패해도 나머지는 계속 진행
            failures.append(f"{sym}: {e}")
        time.sleep(0.3)  # Yahoo 요청 간 최소 텀

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "universe_size": len(symbols),
        "scored": len(scores),
        "failures": failures,
        "scores": scores,
    }

    for d in (model_dir, output_dir):
        with open(os.path.join(d, "scores.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # 앱이 즉시 읽을 수 있도록 고정 키로 S3 직접 업로드 (선택 사항 — 학습 실행 역할에 s3:PutObject 필요)
    bucket = os.environ.get("SCORES_BUCKET")
    if bucket:
        try:
            import boto3
            boto3.client("s3").put_object(
                Bucket=bucket,
                Key="latest/scores.json",
                Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as e:
            print(f"[WARN] S3 직접 업로드 실패 (SM_OUTPUT_DATA_DIR 산출물은 정상 저장됨): {e}")

    print(f"학습 완료: {len(scores)}/{len(symbols)} 종목, 실패 {len(failures)}건")


if __name__ == "__main__":
    main()
