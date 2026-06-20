"""백테스팅 엔진 (5.5단계).

과거 가격 데이터로 '추세 점수 기반 매매 전략'을 시뮬레이션하고
핵심 성과 지표(CAGR · MDD · Sharpe · 승률)를 산출한다.

전략(기본):
  - 추세 점수 ≥ buy_th  → 매수(보유)로 전환
  - 추세 점수 ≤ sell_th → 매도(현금)로 전환
  - 그 사이는 직전 상태 유지

look-ahead 방지: t일 종가로 계산한 신호는 t+1일에 체결한다(당일 신호로 당일 체결 금지).
거래비용: 포지션이 바뀌는 날에 fee(왕복 근사)를 차감한다.

⚠️ 뉴스·선호 점수는 과거 시점 재현이 어려워 여기선 제외(트렌드만 검증).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..analysis import trend_score_series

TRADING_DAYS = 252


@dataclass
class BacktestResult:
    """백테스트 성과 요약."""

    total_return: float       # 전략 총수익률
    cagr: float               # 연복리수익률
    mdd: float                # 최대낙폭(음수)
    sharpe: float             # 연율화 샤프지수
    win_rate: float           # 승률(청산된 거래 기준)
    n_trades: int             # 매수 진입 횟수
    bnh_return: float         # Buy & Hold 총수익률(벤치마크)
    equity: pd.Series         # 전략 누적자산곡선(시작=1.0)
    buy_th: float
    sell_th: float

    @property
    def beats_bnh(self) -> bool:
        return self.total_return > self.bnh_return

    def summary(self) -> str:
        return (
            f"총수익 {self.total_return*100:+.1f}% (B&H {self.bnh_return*100:+.1f}%) · "
            f"CAGR {self.cagr*100:+.1f}% · MDD {self.mdd*100:.1f}% · "
            f"Sharpe {self.sharpe:.2f} · 승률 {self.win_rate*100:.0f}% · 거래 {self.n_trades}회"
        )


def _win_rate(position: pd.Series, close: pd.Series) -> tuple[float, int]:
    """진입~청산 구간별 수익으로 승률과 거래수를 계산한다."""
    entries = position[(position == 1) & (position.shift(1, fill_value=0) == 0)].index
    exits = position[(position == 0) & (position.shift(1, fill_value=0) == 1)].index
    wins = trades = 0
    for i, ent in enumerate(entries):
        # 대응 청산일(없으면 마지막 날까지 보유한 것으로 처리)
        ex = exits[i] if i < len(exits) else close.index[-1]
        if close.loc[ex] > close.loc[ent]:
            wins += 1
        trades += 1
    return (wins / trades if trades else 0.0), trades


def run_backtest(df: pd.DataFrame, score_series: pd.Series | None = None,
                 buy_th: float = 60.0, sell_th: float = 45.0,
                 fee: float = 0.0015) -> BacktestResult:
    """추세 점수 전략을 백테스트한다.

    score_series 를 주면 그걸로, 없으면 trend_score_series(df) 로 신호를 만든다.
    """
    if score_series is None:
        score_series = trend_score_series(df)
    close = df["Close"].astype(float)

    # 1) 목표 상태(target): 점수 임계값으로 보유/현금 결정, 그 사이는 유지
    target = pd.Series(np.nan, index=df.index)
    target[score_series >= buy_th] = 1.0
    target[score_series <= sell_th] = 0.0
    target = target.ffill().fillna(0.0)

    # 2) t일 신호 → t+1일 체결 (look-ahead 방지)
    position = target.shift(1).fillna(0.0)

    # 3) 일별 수익 = 보유일의 가격수익 - 포지션 전환일의 거래비용
    daily_ret = close.pct_change().fillna(0.0)
    strat_ret = position * daily_ret
    switches = position.diff().abs().fillna(0.0)   # 0↔1 전환 시 1
    strat_ret = strat_ret - switches * fee

    equity = (1.0 + strat_ret).cumprod()

    # 4) 성과 지표
    total_return = float(equity.iloc[-1] - 1.0)
    years = max(len(df) / TRADING_DAYS, 1e-9)
    cagr = float(equity.iloc[-1] ** (1 / years) - 1.0)
    drawdown = equity / equity.cummax() - 1.0
    mdd = float(drawdown.min())
    std = strat_ret.std()
    sharpe = float(strat_ret.mean() / std * np.sqrt(TRADING_DAYS)) if std > 0 else 0.0
    win_rate, n_trades = _win_rate(position, close)
    bnh_return = float(close.iloc[-1] / close.iloc[0] - 1.0)

    return BacktestResult(
        total_return=total_return, cagr=cagr, mdd=mdd, sharpe=sharpe,
        win_rate=win_rate, n_trades=n_trades, bnh_return=bnh_return,
        equity=equity, buy_th=buy_th, sell_th=sell_th,
    )
