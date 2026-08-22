"""AWS Comprehend 기반 뉴스/공시 텍스트 감성분석.

boto3 미설치나 자격증명 누락 시 예외를 삼키고 None을 반환한다 — 로컬 개발
환경에서 AWS 자격증명 없이도 크롤링/추천 파이프라인이 정상 동작해야 하기 때문.
"""
import asyncio
from typing import Optional

from app.config import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("comprehend", region_name=settings.AWS_REGION)
    return _client


def _batch_detect(texts: list[str]) -> list[Optional[dict]]:
    client = _get_client()
    results: list[Optional[dict]] = [None] * len(texts)
    # BatchDetectSentiment 제약: 요청당 최대 25건, 건당 최대 5000바이트(UTF-8)
    for start in range(0, len(texts), 25):
        chunk = [t[:4900] for t in texts[start:start + 25]]
        resp = client.batch_detect_sentiment(TextList=chunk, LanguageCode="ko")
        for r in resp.get("ResultList", []):
            idx = start + r["Index"]
            scores = r["SentimentScore"]
            results[idx] = {
                "sentiment": r["Sentiment"],
                "positive": round(scores["Positive"], 4),
                "negative": round(scores["Negative"], 4),
            }
    return results


async def analyze_sentiment(texts: list[str]) -> list[Optional[dict]]:
    """텍스트 목록의 감성을 분석한다. 실패 시 전부 None으로 채운 리스트를 반환."""
    if not texts:
        return []
    try:
        return await asyncio.to_thread(_batch_detect, texts)
    except Exception:
        return [None] * len(texts)


def aggregate_sentiment_score(results: list[Optional[dict]]) -> Optional[float]:
    """(긍정 비율 - 부정 비율), 범위 [-1, 1]. 유효 결과가 없으면 None."""
    valid = [r for r in results if r]
    if not valid:
        return None
    pos = sum(1 for r in valid if r["sentiment"] == "POSITIVE")
    neg = sum(1 for r in valid if r["sentiment"] == "NEGATIVE")
    return round((pos - neg) / len(valid), 4)
