"""모의투자 자동운용 (시그널 → 자동 매수/매도).

펀드매니저처럼: 관심종목을 분석해 매수 시그널이면 사고, 매도 시그널이면 판다.
포지션 사이징: 종목당 초기자본의 일정 비율(기본 20%)까지만 — 분산해 한 종목 몰빵 방지.
⚠️ 가상계좌 전용. 실거래 아님.
"""
from __future__ import annotations

from ..data.base import DataSource
from ..news.base import NewsSource
from ..profile import UserProfile, THEMES
from ..signal import analyze_symbol
from .account import PaperAccount

# 미국 종목 가격(USD)을 원화 계좌로 환산할 고정 환율.
# TODO: fdr.DataReader('USD/KRW') 로 실시간 환율 반영 (지금은 단순/투명하게 고정)
FX_USD_KRW = 1350.0


def to_krw(price: float, market: str) -> float:
    """종목 가격을 원화로 환산한다(미국=USD→KRW)."""
    return price * FX_USD_KRW if market == "US" else price


def target_universe(profile: UserProfile) -> list[str]:
    """운용 대상 종목 = 즐겨찾기 ∪ 선호 테마의 대표 종목."""
    universe = set(profile.favorites)
    for theme in profile.theme_weights:
        universe.update(THEMES.get(theme, {}).get("symbols", set()))
    return sorted(universe)


def run_paper_trading(account: PaperAccount, profile: UserProfile,
                      data_source: DataSource, news_source: NewsSource,
                      symbols: list[str] | None = None,
                      pos_pct: float = 0.20,
                      weights: dict[str, float] | None = None) -> tuple[list[dict], dict]:
    """관심종목을 분석해 시그널대로 가상 매매한다.

    반환: (체결내역 리스트, 종목별 현재가 dict)
    """
    symbols = symbols or target_universe(profile)
    trades: list[dict] = []
    prices: dict[str, float] = {}
    actions: dict[str, tuple[str, str]] = {}  # symbol -> (action, name)

    # 1) 전 종목 분석 (현재가 원화환산 + 시그널 수집)
    for sym in symbols:
        try:
            a = analyze_symbol(sym, profile, data_source, news_source, weights=weights)
            prices[sym] = to_krw(a.price.last_close, a.price.market)
            actions[sym] = (a.signal.action, a.price.name)
        except Exception:  # noqa: BLE001 - 한 종목 실패가 전체를 막지 않게
            continue

    # 2) 매도 먼저 (현금 확보) — 보유 중 매도 시그널
    for sym, (action, name) in actions.items():
        if action == "매도" and sym in account.holdings:
            rec = account.sell(sym, prices[sym], name=name)
            if rec:
                trades.append(rec)

    # 3) 매수 — 미보유 중 매수 시그널, 종목당 배분액까지
    budget = account.initial_capital * pos_pct
    for sym, (action, name) in actions.items():
        if action == "매수" and sym not in account.holdings:
            rec = account.buy(sym, prices[sym], krw_amount=min(budget, account.cash), name=name)
            if rec:
                trades.append(rec)

    return trades, prices
