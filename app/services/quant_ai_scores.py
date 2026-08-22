"""SageMaker 배치 학습(퀀트 유니버스 전종목 재학습) 결과를 S3에서 읽어온다.

일 1회 SageMaker Training Job(sagemaker/train.py)이 산출한 scores.json을
캐시(1시간)와 함께 조회한다. 버킷 미설정이나 boto3/자격증명 문제 시 조용히
None을 반환하며, 호출측(robo_allocation)은 실시간 계산만으로 순위를 매기는
방식으로 대체한다 — 배치 학습 결과는 있으면 쓰는 보조 시그널이지 필수 의존성이 아니다.
"""
import asyncio
import time
from typing import Optional

from app.config import settings

_cache: dict = {"data": None, "ts": 0.0}
_TTL_SEC = 3600


def _fetch_sync() -> Optional[dict]:
    import json
    import boto3

    client = boto3.client("s3", region_name=settings.AWS_REGION)
    obj = client.get_object(Bucket=settings.ML_ARTIFACTS_BUCKET, Key="latest/scores.json")
    return json.loads(obj["Body"].read())


async def get_batch_training_scores() -> Optional[dict]:
    """{"generated_at", "scores": {symbol: {pred_ann_return_pct, cls_val_accuracy, ...}}} 또는 None."""
    if not settings.ML_ARTIFACTS_BUCKET:
        return None

    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < _TTL_SEC:
        return _cache["data"]

    try:
        data = await asyncio.to_thread(_fetch_sync)
    except Exception:
        return _cache["data"]  # 조회 실패 시 있으면 stale 캐시라도 사용, 없으면 None

    _cache["data"], _cache["ts"] = data, now
    return data
