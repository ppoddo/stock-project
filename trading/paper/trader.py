"""모의투자 자동운용 (시그널 → 자동 매수/매도).

펀드매니저처럼: 관심종목을 분석해 매수 시그널이면 사고, 매도 시그널이면 판다.
포지션 사이징: 종목당 초기자본의 일정 비율(기본 20%)까지만 — 분산해 한 종목 몰빵 방지.

WP2 수식 개선:
  - 손절/트레일링 스탑으로 강제 청산(시그널과 무관하게 손실 확대 차단).
  - 매도 판정은 선호도 제외 재가중 점수(sell_signal) 기준 — 하락 종목을 선호가 떠받치던 구조 제거.
  - 실시간 환율(USD/KRW) 조회, 실패 시 폴백.
  - 매도(모든 사유) 후 재진입 쿨다운(영업일 N일).
  - 매수 후 최소 보유기간(영업일) 내 시그널 매도 보류 — 장중 왕복 방지(손절은 예외).
⚠️ 가상계좌 전용. 실거래 아님.
"""
from __future__ import annotations

from datetime import date

import numpy as np

from ..config import (
    CASH_BUFFER_PCT,
    FX_USD_KRW_FALLBACK,
    MAX_POSITIONS,
    MIN_HOLD_BDAYS,
    POSITION_PCT,
    REENTRY_COOLDOWN_DAYS,
    STOP_LOSS_PCT,
    THEME_CAP,
    TRAILING_STOP_PCT,
)
from ..data.base import DataSource
from ..news.base import NewsSource
from ..profile import UserProfile, THEMES
from ..profile.themes import symbol_themes
from ..signal import analyze_symbol
from .account import PaperAccount
from .thesis import build_thesis


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
    # symbol -> {buy, sell, name, scores, df} — scores·df 는 매매 계획서(thesis) 재료
    actions: dict[str, dict] = {}

    fx = resolve_fx(data_source)
    today = date.today().isoformat()

    # 1) 전 종목 분석 (현재가 원화환산 + 매수/매도 시그널 분리 수집)
    for sym in symbols:
        try:
            a = analyze_symbol(sym, profile, data_source, news_source, weights=weights)
            prices[sym] = to_krw(a.price.last_close, a.price.market, fx)
            sell_act = a.sell_signal.action if a.sell_signal else a.signal.action
            actions[sym] = {
                "buy": a.signal.action, "sell": sell_act, "name": a.price.name,
                "scores": {"trend": a.trend.score, "news": a.news.score,
                           "pref": a.pref.score, "total": a.signal.total},
                "df": a.price.df,
            }
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
        name = actions.get(sym, {}).get("name", "")
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
    #    매수 후 MIN_HOLD_BDAYS 영업일 내엔 보류 — 장중 점수 흔들림에 의한
    #    당일 매수→매도 왕복 방지(2026-07-08 회고). 손절·트레일링(3단계)은 예외 없이 동작.
    for sym, info in actions.items():
        if sym in account.holdings and info["sell"] == "매도":
            if in_cooldown(account.holdings[sym].buy_date, today, MIN_HOLD_BDAYS):
                continue  # 최소 보유기간 미경과 — 시그널 매도 보류
            rec = account.sell(sym, prices[sym], name=info["name"], reason="시그널(선호제외)")
            if rec:
                trades.append(rec)
                account.cooldowns[sym] = today  # 모든 매도에 재매수 쿨다운(왕복 방지)

    # 5) 시그널 매수 — 점수 랭킹순 + 포트폴리오 캡 (execute_buys 로 분리, 테스트 가능)
    trades.extend(execute_buys(account, actions, prices, today, pos_pct))

    return trades, prices


def blocked_by_theme_cap(symbol: str, holdings, cap: int = THEME_CAP) -> bool:
    """이 종목의 테마 중 하나라도 이미 cap 개 보유 중이면 True(신규 매수 차단).

    같은 테마 몰빵(섹터 동반 하락)의 직접 처방 — 2026-07-08 사용자 진단.
    """
    for theme in symbol_themes(symbol):
        n = sum(1 for held in holdings if theme in symbol_themes(held))
        if n >= cap:
            return True
    return False


def execute_buys(account: PaperAccount, actions: dict, prices: dict[str, float],
                 today: str, pos_pct: float = POSITION_PCT) -> list[dict]:
    """매수 실행 — 종합점수 내림차순 랭킹 + 3중 캡.

    규칙(위반 시 매수 안 함):
      1. 점수 높은 후보부터 — 스캔 순서가 아니라 확신이 큰 순서로 현금을 쓴다
      2. MAX_POSITIONS: 동시 보유 종목 수 상한
      3. THEME_CAP: 같은 테마 보유 상한
      4. CASH_BUFFER_PCT: 초기자본의 일정 비율은 항상 현금으로 남긴다
    actions/prices 만 받아 네트워크 없이 동작한다(단위 테스트 가능).
    """
    trades: list[dict] = []
    budget = account.initial_capital * pos_pct
    reserve = account.initial_capital * CASH_BUFFER_PCT

    candidates = [(sym, info) for sym, info in actions.items()
                  if info["buy"] == "매수" and sym not in account.holdings
                  and not in_cooldown(account.cooldowns.get(sym), today,
                                      REENTRY_COOLDOWN_DAYS)]
    candidates.sort(key=lambda x: x[1]["scores"]["total"], reverse=True)  # 1) 랭킹

    for sym, info in candidates:
        if len(account.holdings) >= MAX_POSITIONS:      # 2) 종목 수 상한
            break
        if blocked_by_theme_cap(sym, account.holdings):  # 3) 테마 캡
            continue
        available = account.cash - reserve               # 4) 현금 버퍼
        if available <= 0:
            break
        try:
            thesis = build_thesis(info["df"], prices[sym], info["scores"])
        except Exception:  # noqa: BLE001 - 계획서 실패가 매매를 막지 않게
            thesis = None
        rec = account.buy(sym, prices[sym], krw_amount=min(budget, available),
                          name=info["name"], thesis=thesis)
        if rec:
            trades.append(rec)
    return trades
