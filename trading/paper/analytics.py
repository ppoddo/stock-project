"""모의투자 성과 분석 (진단 리포트).

계좌를 현재가로 재평가(mark-to-market)하고 종목별 손익·기여도,
journal 시계열 기반 총수익률·MDD·일별 변동을 계산해 "왜 이 성과인지" reasons 로 설명한다.
데이터가 1행뿐이어도(운용 초기) 에러 없이 부분 결과 + "데이터 축적 중" 안내를 낸다.
⚠️ 가상계좌 분석 전용.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..profile.themes import display_name, symbol_themes
from .account import PaperAccount


@dataclass
class PositionPnL:
    """종목별 손익 + 전체 손익 기여도."""

    symbol: str
    name: str
    shares: int
    avg_price: float
    cur_price: float
    pnl: float                 # 평가손익(원)
    pnl_pct: float             # 수익률
    contribution: float        # 전체 손익 대비 이 종목의 기여(원, 부호 유지)


@dataclass
class PerformanceReport:
    """계좌 성과 분석 결과."""

    total_value: float
    total_return: float        # 초기자본 대비
    cash: float
    positions: list[PositionPnL]
    mdd: float                 # journal 시계열 기반 최대낙폭(음수), 데이터 부족 시 0.0
    days_tracked: int          # journal 레코드 수
    best: PositionPnL | None
    worst: PositionPnL | None
    reasons: list[str] = field(default_factory=list)
    data_sufficient: bool = True   # journal >= 2 여야 시계열 지표 신뢰


def name_of(account: PaperAccount, symbol: str) -> str:
    """종목 표시명: 한글 사전 우선, 없으면 history 의 기록명, 그것도 없으면 코드."""
    for rec in reversed(account.history):
        if rec.get("symbol") == symbol and rec.get("name"):
            return display_name(symbol, rec["name"])
    return display_name(symbol)


def _max_drawdown(totals: list[float]) -> float:
    """총자산 시퀀스의 러닝 피크 대비 최대낙폭(음수)을 계산한다."""
    peak = float("-inf")
    mdd = 0.0
    for t in totals:
        peak = max(peak, t)
        if peak > 0:
            mdd = min(mdd, t / peak - 1.0)
    return mdd


def analyze_performance(account: PaperAccount, prices: dict[str, float],
                        equity_history: list[dict] | None = None) -> PerformanceReport:
    """계좌를 현재가로 평가하고 종목별 손익·기여도·MDD·근거를 산출한다.

    prices: symbol -> 원화환산 현재가 (없는 종목은 avg_price 로 폴백; account.position_pnl 규약과 동일)
    equity_history: journal.load_equity_history() 결과. None/1행이면 시계열 지표는 0, data_sufficient=False.
    """
    total_value = account.total_value(prices)
    total_return = account.total_return(prices)
    cash = account.cash

    # ── 종목별 손익 ──────────────────────────────────────
    positions: list[PositionPnL] = []
    for sym, h in account.holdings.items():
        px = prices.get(sym, h.avg_price)
        pnl, pnl_pct = account.position_pnl(sym, px)
        positions.append(PositionPnL(
            symbol=sym,
            name=name_of(account, sym),
            shares=h.shares,
            avg_price=h.avg_price,
            cur_price=px,
            pnl=pnl,
            pnl_pct=pnl_pct,
            contribution=pnl,   # 전체 손익합에 대한 부호별 기여
        ))

    best = max(positions, key=lambda p: p.pnl) if positions else None
    worst = min(positions, key=lambda p: p.pnl) if positions else None

    # ── journal 시계열 기반 MDD ───────────────────────────
    history = equity_history or []
    days_tracked = len(history)
    data_sufficient = days_tracked >= 2
    if data_sufficient:
        totals = [rec.get("total", 0.0) for rec in history]
        mdd = _max_drawdown(totals)
    else:
        mdd = 0.0

    # ── 진단 reasons (한국어) ─────────────────────────────
    reasons: list[str] = [
        f"총자산 {total_value:,.0f}원 · {total_return * 100:+.2f}% (초기 대비)",
    ]

    if worst is not None and worst.pnl < 0:
        reasons.append(
            f"발목을 잡는 종목 — 가장 큰 손실: {worst.name} "
            f"{worst.pnl_pct * 100:+.1f}% ({worst.pnl:,.0f}원)"
        )
    elif worst is not None:
        reasons.append(
            f"가장 부진한 종목: {worst.name} "
            f"{worst.pnl_pct * 100:+.1f}% ({worst.pnl:,.0f}원)"
        )

    # 섹터(테마) 집중 경고 — 손실원인 1 진단
    if positions:
        theme_counts: dict[str, int] = {}
        for p in positions:
            for theme in symbol_themes(p.symbol):
                theme_counts[theme] = theme_counts.get(theme, 0) + 1
        tot = len(positions)
        if theme_counts:
            top_theme, top_n = max(theme_counts.items(), key=lambda kv: kv[1])
            if top_n * 2 > tot:   # 과반
                reasons.append(
                    f"⚠️ 보유가 '{top_theme}' 테마에 {top_n}/{tot}종목 집중 "
                    f"— 섹터 동반 하락에 취약"
                )

    # 전 종목 손실 경고
    if positions and all(p.pnl < 0 for p in positions):
        reasons.append(
            "보유 전 종목 평가손실 — 손절 규칙 부재 가능성(WP2에서 개선)"
        )

    # 데이터 부족 안내
    if not data_sufficient:
        reasons.append(
            f"자산 시계열 {days_tracked}일치뿐 — MDD·변동성은 데이터가 쌓이면 정확해집니다"
        )

    return PerformanceReport(
        total_value=total_value,
        total_return=total_return,
        cash=cash,
        positions=positions,
        mdd=mdd,
        days_tracked=days_tracked,
        best=best,
        worst=worst,
        reasons=reasons,
        data_sufficient=data_sufficient,
    )
