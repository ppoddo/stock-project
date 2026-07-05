"""모의투자 자동운용 (시그널 → 자동 매수/매도).

펀드매니저처럼: 관심종목을 분석해 매수 시그널이면 사고, 매도 시그널이면 판다.
포지션 사이징: 종목당 초기자본의 일정 비율(기본 20%)까지만 — 분산해 한 종목 몰빵 방지.

WP2 수식 개선:
  - 손절/트레일링 스탑으로 강제 청산(시그널과 무관하게 손실 확대 차단).
  - 매도 판정은 선호도 제외 재가중 점수(sell_signal) 기준 — 하락 종목을 선호가 떠받치던 구조 제거.
  - 실시간 환율(USD/KRW) 조회, 실패 시 폴백.
  - 손절 후 재진입 쿨다운(영업일 N일).
⚠️ 가상계좌 전용. 실거래 아님.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from ..config import (
    FX_USD_KRW_FALLBACK,
    POSITION_PCT,
    REENTRY_COOLDOWN_DAYS,
    STOP_LOSS_PCT,
    TRAILING_STOP_PCT,
)
from ..data.base import DataSource
from ..news.base import NewsSource
from ..profile import UserProfile, THEMES
from ..signal import analyze_symbol
from .account import PaperAccount


def resolve_fx(data_source: DataSource) -> float:
    """실시간 USD/KRW 환율. 조회 실패/비정상 시 폴백 환율 사용."""
    fx = data_source.get_fx("USD/KRW")
    return fx if fx and fx > 0 else FX_USD_KRW_FALLBACK


def to_krw(price: float, market: str, fx: float = FX_USD_KRW_FALLBACK) -> float:
    """종목 가격을 원화로 환산한다(미국=USD→KRW). fx 미지정 시 폴백 환율."""
    return price * fx if market == "US" else price


def in_cooldown(last_sold_iso: str | None, today_iso: str, days: int) -> bool:
    """마지막 손절일로부터 영업일 days 이내면 True(재매수 금지).

    주말은 numpy busday 로 자동 제외. 공휴일은 무시(근사) — 영업일 기준.
    """
    if not last_sold_iso:
        return False
    bdays = int(np.busday_count(last_sold_iso[:10], today_iso[:10]))
    return bdays < days


def target_universe(profile: UserProfile) -> list[str]:
    """운용 대상 종목 = 즐겨찾기 ∪ 선호 테마의 대표 종목."""
    universe = set(profile.favorites)
    for theme in profile.theme_weights:
        universe.update(THEMES.get(theme, {}).get("symbols", set()))
    return sorted(universe)


def run_paper_trading(account: PaperAccount, profile: UserProfile,
                      data_source: DataSource, news_source: NewsSource,
                      symbols: list[str] | None = None,
                      pos_pct: float = POSITION_PCT,
                      weights: dict[str, float] | None = None) -> tuple[list[dict], dict]:
    """관심종목을 분석해 시그널대로 가상 매매한다.

    매매 순서(WP2): 1)분석 → 2)트레일링 고점 갱신 → 3)강제청산(손절/트레일링)
                    → 4)시그널 매도(선호 제외) → 5)시그널 매수(쿨다운 필터).
    반환: (체결내역 리스트, 종목별 현재가 dict)
    """
    symbols = symbols or target_universe(profile)
    trades: list[dict] = []
    prices: dict[str, float] = {}
    # symbol -> (매수시그널 action, 매도시그널 action, name)
    actions: dict[str, tuple[str, str, str]] = {}

    fx = resolve_fx(data_source)
    today = date.today().isoformat()

    # 1) 전 종목 분석 (현재가 원화환산 + 매수/매도 시그널 분리 수집)
    for sym in symbols:
        try:
            a = analyze_symbol(sym, profile, data_source, news_source, weights=weights)
            prices[sym] = to_krw(a.price.last_close, a.price.market, fx)
            sell_act = a.sell_signal.action if a.sell_signal else a.signal.action
            actions[sym] = (a.signal.action, sell_act, a.price.name)
        except Exception:  # noqa: BLE001 - 한 종목 실패가 전체를 막지 않게
            continue

    # 2) 트레일링 고점 갱신 (보유 종목)
    for sym, h in account.holdings.items():
        if sym in prices:
            h.peak_price = max(h.peak_price or h.avg_price, prices[sym])

    # 3) 강제 청산 — 손절/트레일링 (시그널 무관, 손실 확대 차단)
    for sym in list(account.holdings):
        if sym not in prices:
            continue
        h = account.holdings[sym]
        px = prices[sym]
        name = actions.get(sym, (None, None, ""))[2]
        down_from_avg = px / h.avg_price - 1.0 if h.avg_price else 0.0
        peak = h.peak_price or h.avg_price
        down_from_peak = px / peak - 1.0 if peak else 0.0
        rec = None
        if down_from_avg <= -STOP_LOSS_PCT:
            rec = account.sell(sym, px, name=name, reason=f"손절(-{STOP_LOSS_PCT:.0%})")
            account.cooldowns[sym] = today
        elif down_from_peak <= -TRAILING_STOP_PCT:
            rec = account.sell(sym, px, name=name, reason=f"트레일링(-{TRAILING_STOP_PCT:.0%})")
            account.cooldowns[sym] = today
        if rec:
            trades.append(rec)

    # 4) 시그널 매도 — 선호 제외 매도점수 기준 (남은 보유 종목)
    for sym, (buy_act, sell_act, name) in actions.items():
        if sym in account.holdings and sell_act == "매도":
            rec = account.sell(sym, prices[sym], name=name, reason="시그널(선호제외)")
            if rec:
                trades.append(rec)

    # 5) 시그널 매수 — 미보유 + 매수시그널 + 쿨다운 경과
    budget = account.initial_capital * pos_pct
    for sym, (buy_act, sell_act, name) in actions.items():
        if buy_act == "매수" and sym not in account.holdings:
            if in_cooldown(account.cooldowns.get(sym), today, REENTRY_COOLDOWN_DAYS):
                continue  # 손절 후 N영업일 내 재매수 금지
            rec = account.buy(sym, prices[sym],
                              krw_amount=min(budget, account.cash), name=name)
            if rec:
                trades.append(rec)

    return trades, prices
