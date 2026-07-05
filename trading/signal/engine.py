"""종합 시그널 엔진 (요구사항 종합 · 4단계).

세 분석 점수를 가중 합산해 0~100 종합 점수와 매수/관망/매도 행동을 낸다.
  종합점수 = 추세*w_t + 뉴스*w_n + 선호도*w_p   (가중치 합 = 1)

가중치 기본값은 5단계 백테스팅으로 튜닝한다. 그 전엔 추세 우선·투명하게.
analyze_symbol() 은 대시보드와 감시 워커가 공유하는 단일 진입점이다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import BUY_THRESHOLD, SELL_THRESHOLD
from ..data.base import DataSource, PriceData
from ..news.base import NewsSource
from ..analysis import trend_score, TrendResult
from ..news import news_score, NewsResult
from ..profile import UserProfile, preference_score, PreferenceResult

# 기본 가중치 (합 1.0). 추세를 가장 신뢰.
DEFAULT_WEIGHTS = {"trend": 0.5, "news": 0.3, "pref": 0.2}

# 행동 임계값 (종합점수 기준) — 단일 출처는 trading/config.py (WP0)


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


def reweight_without_pref(weights: dict[str, float]) -> dict[str, float]:
    """선호(pref) 가중치를 뺀 뒤 합이 1이 되도록 추세·뉴스를 재정규화한다.

    공식: w' = {trend: w_t/(w_t+w_n), news: w_n/(w_t+w_n), pref: 0.0}
    분모가 0이면(둘 다 0) 추세 100% 로 폴백.
    """
    wt, wn = weights.get("trend", 0.0), weights.get("news", 0.0)
    denom = wt + wn
    if denom <= 0:
        return {"trend": 1.0, "news": 0.0, "pref": 0.0}
    return {"trend": wt / denom, "news": wn / denom, "pref": 0.0}


def sell_score(trend: float, news: float,
               weights: dict[str, float] | None = None) -> SignalResult:
    """매도 판정용 종합점수: 선호 제외 재가중(추세·뉴스만).

    선호도 20%가 하락 종목을 떠받치던 구조를 제거해 매도 판단을 예민하게 한다.
    """
    w = reweight_without_pref(weights or DEFAULT_WEIGHTS)
    return combine_scores(trend, news, 0.0, w)   # pref=0, 가중치도 0이라 무영향


@dataclass
class Analysis:
    """한 종목의 전체 분석 묶음 (가격 + 세 분석 + 종합 시그널)."""

    price: PriceData
    trend: TrendResult
    news: NewsResult
    pref: PreferenceResult
    signal: SignalResult
    sell_signal: SignalResult | None = None   # 매도 판정용(선호 제외 재가중)


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
    # 매도 판정용 점수: 선호 제외 재가중(추세·뉴스만) — WP2
    sell_sig = sell_score(trend.score, news.score, weights)
    return Analysis(price=price, trend=trend, news=news, pref=pref,
                    signal=signal, sell_signal=sell_sig)
