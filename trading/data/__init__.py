"""데이터 소스 모듈.

get_source() 로 데이터 소스 구현체를 받아 쓴다.
나중에 다른 소스(증권사 API 등)로 교체해도 분석/전략 코드는 그대로 둔다.
"""
from .base import DataSource, PriceData
from .fdr_source import FdrSource


def get_source(name: str = "fdr") -> DataSource:
    """이름으로 데이터 소스 구현체를 반환한다."""
    sources = {
        "fdr": FdrSource,
    }
    if name not in sources:
        raise ValueError(f"알 수 없는 데이터 소스: {name} (가능: {list(sources)})")
    return sources[name]()


__all__ = ["DataSource", "PriceData", "FdrSource", "get_source"]
