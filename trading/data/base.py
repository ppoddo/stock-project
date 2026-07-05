"""데이터 소스 추상 인터페이스.

모든 데이터 소스는 DataSource 를 상속해 같은 메서드를 제공한다.
이렇게 추상화해 두면, 나중에 FinanceDataReader -> 증권사 API 로 바꿔도
분석/전략 코드는 한 줄도 안 고쳐도 된다. (1단계 핵심 설계)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class PriceData:
    """한 종목의 가격 시계열 + 메타정보."""

    symbol: str          # 종목코드 (예: '005930', 'AAPL')
    name: str            # 표시용 이름
    market: str          # 'KR' | 'US'
    df: pd.DataFrame     # 인덱스=날짜, 컬럼=[Open, High, Low, Close, Volume]

    @property
    def last_close(self) -> float:
        return float(self.df["Close"].iloc[-1])


class DataSource(ABC):
    """가격/종목 데이터를 제공하는 소스의 공통 인터페이스."""

    @abstractmethod
    def get_price(self, symbol: str, start: str, end: str | None = None) -> PriceData:
        """한 종목의 일봉 데이터를 가져온다. start/end 는 'YYYY-MM-DD'."""
        raise NotImplementedError

    @abstractmethod
    def detect_market(self, symbol: str) -> str:
        """종목코드로 시장('KR'/'US')을 추정한다."""
        raise NotImplementedError

    @abstractmethod
    def get_name(self, symbol: str) -> str:
        """종목코드를 표시용 이름으로 바꾼다. 뉴스 검색어로도 쓰인다."""
        raise NotImplementedError

    def get_fx(self, pair: str = "USD/KRW") -> float | None:
        """환율을 조회한다. 실패/미지원 시 None.

        기본 구현은 None(선택 기능) — 다른/미래 소스가 강제 구현하지 않아도 되게
        추상 아닌 일반 메서드로 둔다. 전략 코드는 이 메서드만 호출하고 폴백을 갖는다.
        """
        return None
