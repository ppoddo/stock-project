"""종합 시그널 엔진 (요구사항 종합 · 4단계).

세 분석 점수를 가중 합산해 0~100 종합 점수와 매수/관망/매도 행동을 낸다.
  종합점수 = 추세*w_t + 뉴스*w_n + 선호도*w_p   (가중치 합 = 1)

가중치 기본값은 5단계 백테스팅으로 튜닝한다. 그 전엔 추세 우선·투명하게.
analyze_symbol() 은 대시보드와 감시 워커가 공유하는 단일 진입점이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data.base import DataSource, PriceData
from ..news.base import NewsSource
from ..analysis import trend_score, TrendResult
from ..news import news_score, NewsResult
from ..profile import UserProfile, preference_score, PreferenceResult

# 기본 가중치 (합 1.0). 추세를 가장 신뢰.
DEFAULT_WEIGHTS = {"trend": 0.5, "news": 0.3, "pref": 0.2}

# 행동 임계값 (종합점수 기준)
BUY_THRESHOLD = 70.0
SELL_THRESHOLD = 40.0


@dataclass
class SignalResult:
    """종합 시그널 결과."""

    total: float                 # 0~100 종합 점수
    action: str                  # "매수" | "관망" | "매도"
    trend: float
    news: float
    pref: float
    weights: dict[str, float]
    reasons: list[str] = field(default_factory=list)

    @property
    def emoji(self) -> str:
        return {"매수": "🟢", "관망": "🟡", "매도": "🔴"}.get(self.action, "⚪")


def decide_action(total: float) -> str:
    if total >= BUY_THRESHOLD:
        return "매수"
    if total < SELL_THRESHOLD:
        return "매도"
    return "관망"


def combine_scores(trend: float, news: float, pref: float,
                   weights: dict[str, float] | None = None) -> SignalResult:
    """세 점수를 가중 합산해 종합 시그널을 만든다."""
    w = weights or DEFAULT_WEIGHTS
    total = trend * w["trend"] + news * w["news"] + pref * w["pref"]
    total = round(total, 1)
    action = decide_action(total)
    reasons = [
        f"추세 {trend} × {w['trend']:.0%} + 뉴스 {news} × {w['news']:.0%} "
        f"+ 선호 {pref} × {w['pref']:.0%} = {total}",
    ]
    return SignalResult(total=total, action=action, trend=trend, news=news,
                        pref=pref, weights=w, reasons=reasons)


@dataclass
class Analysis:
    """한 종목의 전체 분석 묶음 (가격 + 세 분석 + 종합 시그널)."""

    price: PriceData
    trend: TrendResult
    news: NewsResult
    pref: PreferenceResult
    signal: SignalResult


def analyze_symbol(symbol: str, profile: UserProfile,
                   data_source: DataSource, news_source: NewsSource,
                   start: str = "2023-01-01",
                   weights: dict[str, float] | None = None) -> Analysis:
    """종목 하나를 끝까지 분석한다. 대시보드·감시 워커 공용 진입점."""
    price = data_source.get_price(symbol, start=start)
    trend = trend_score(price.df)
    news = news_score(news_source.search(price.name, market=price.market, limit=30))
    pref = preference_score(symbol, profile)
    signal = combine_scores(trend.score, news.score, pref.score, weights)
    return Analysis(price=price, trend=trend, news=news, pref=pref, signal=signal)
