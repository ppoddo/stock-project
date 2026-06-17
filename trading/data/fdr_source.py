"""FinanceDataReader 기반 데이터 소스 구현."""
from __future__ import annotations

import re
from datetime import date

import FinanceDataReader as fdr

from .base import DataSource, PriceData


class FdrSource(DataSource):
    """FinanceDataReader 로 한국/미국 주가·ETF 데이터를 가져온다."""

    def detect_market(self, symbol: str) -> str:
        # 한국 종목코드는 숫자 6자리(예: 005930). 그 외는 미국 티커로 본다.
        return "KR" if re.fullmatch(r"\d{6}", symbol) else "US"

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
            name=symbol,  # 이름 조회는 다음 단계에서 종목 마스터로 보강
            market=self.detect_market(symbol),
            df=df,
        )
