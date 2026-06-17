"""뉴스 소스 추상 인터페이스.

데이터 소스와 동일하게, 뉴스도 인터페이스로 추상화한다.
나중에 네이버 금융·유료 뉴스 API 등으로 교체해도 분석 코드는 그대로 둔다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    """뉴스 기사 한 건."""

    title: str
    link: str
    published: datetime | None
    source: str            # 언론사/출처
    summary: str = ""      # 요약/본문 일부 (있으면)

    @property
    def text(self) -> str:
        """감성 분석 대상 텍스트 (제목 + 요약)."""
        return f"{self.title} {self.summary}".strip()


class NewsSource(ABC):
    """종목 관련 뉴스를 제공하는 소스의 공통 인터페이스."""

    @abstractmethod
    def search(self, query: str, market: str = "KR", limit: int = 30) -> list[NewsItem]:
        """검색어(종목명/코드)로 최근 뉴스를 가져온다.

        market: 'KR' | 'US' — 언어/지역 설정에 사용.
        """
        raise NotImplementedError
