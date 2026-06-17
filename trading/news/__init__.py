"""뉴스 호재 분석 모듈 (요구사항 ②).

get_news_source() 로 뉴스 소스를 받아 종목 뉴스를 가져오고,
news_score() 로 0~100 호재 점수를 매긴다.
"""
from .base import NewsItem, NewsSource
from .google_news import GoogleNewsSource
from .sentiment import news_score, NewsResult


def get_news_source(name: str = "google") -> NewsSource:
    """이름으로 뉴스 소스 구현체를 반환한다."""
    sources = {
        "google": GoogleNewsSource,
    }
    if name not in sources:
        raise ValueError(f"알 수 없는 뉴스 소스: {name} (가능: {list(sources)})")
    return sources[name]()


__all__ = [
    "NewsItem", "NewsSource", "GoogleNewsSource",
    "news_score", "NewsResult", "get_news_source",
]
