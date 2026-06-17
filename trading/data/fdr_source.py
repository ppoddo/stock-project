"""FinanceDataReader 기반 데이터 소스 구현."""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache

import FinanceDataReader as fdr

from .base import DataSource, PriceData


@lru_cache(maxsize=1)
def _krx_listing():
    """KRX 종목 마스터(코드↔이름). 최초 1회만 받아 캐시한다."""
    return fdr.StockListing("KRX").set_index("Code")["Name"].to_dict()


class FdrSource(DataSource):
    """FinanceDataReader 로 한국/미국 주가·ETF 데이터를 가져온다."""

    def detect_market(self, symbol: str) -> str:
        # 한국 종목코드는 숫자 6자리(예: 005930). 그 외는 미국 티커로 본다.
        return "KR" if re.fullmatch(r"\d{6}", symbol) else "US"

    def get_name(self, symbol: str) -> str:
        """종목코드 -> 표시용 이름. 한국 종목은 마스터에서 조회, 실패 시 코드 그대로."""
        if self.detect_market(symbol) == "KR":
            try:
                return _krx_listing().get(symbol, symbol)
            except Exception:  # noqa: BLE001 - 마스터 조회 실패해도 코드로 동작
                return symbol
        return symbol  # 미국은 티커 자체를 검색어로 사용

    def get_price(self, symbol: str, start: str, end: str | None = None) -> PriceData:
        end = end or date.today().isoformat()
        df = fdr.DataReader(symbol, start, end)
        if df.empty:
            raise ValueError(f"데이터를 찾을 수 없음: {symbol}")
        # 컬럼 표준화: 필요한 것만 추리고 결측 제거
        cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        df = df[cols].dropna()
        return PriceData(
            symbol=symbol,
            name=self.get_name(symbol),
            market=self.detect_market(symbol),
            df=df,
        )
