"""구글 뉴스 RSS 기반 뉴스 소스 (한/미 통합, API 키 불필요)."""
from __future__ import annotations

import urllib.parse
from datetime import datetime
from time import mktime

import feedparser

from .base import NewsItem, NewsSource

# 시장별 구글 뉴스 지역/언어 설정
_LOCALE = {
    "KR": {"hl": "ko", "gl": "KR", "ceid": "KR:ko", "suffix": "주가"},
    "US": {"hl": "en-US", "gl": "US", "ceid": "US:en", "suffix": "stock"},
}


class GoogleNewsSource(NewsSource):
    """구글 뉴스 RSS 검색으로 종목 뉴스를 가져온다."""

    def search(self, query: str, market: str = "KR", limit: int = 30) -> list[NewsItem]:
        loc = _LOCALE.get(market, _LOCALE["KR"])
        # 종목명 + 시장별 접미어(주가/stock)로 금융 뉴스 위주로 좁힌다
        q = f"{query} {loc['suffix']}"
        url = (
            "https://news.google.com/rss/search?"
            + urllib.parse.urlencode(
                {"q": q, "hl": loc["hl"], "gl": loc["gl"], "ceid": loc["ceid"]}
            )
        )
        feed = feedparser.parse(url)
        items: list[NewsItem] = []
        for e in feed.entries[:limit]:
            published = None
            if getattr(e, "published_parsed", None):
                published = datetime.fromtimestamp(mktime(e.published_parsed))
            # 구글 뉴스 제목은 "제목 - 언론사" 형식
            title = e.title
            src = getattr(getattr(e, "source", None), "title", "") or ""
            if not src and " - " in title:
                title, src = title.rsplit(" - ", 1)
            items.append(NewsItem(
                title=title.strip(),
                link=e.link,
                published=published,
                source=src.strip(),
                summary=getattr(e, "summary", ""),
            ))
        return items
