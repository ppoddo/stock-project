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
from ..config import BT_BUY_TH, BT_SELL_TH, FEE

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
    stop_loss: float | None = None   # 손절률(WP3, 없으면 손절 미적용)
    avg_hold_days: float = 0.0       # 거래당 평균 보유 영업일 — 매매 계획서(예상 회수일) 근거
    avg_trade_return: float = 0.0    # 거래당 평균 수익률 — 매매 계획서(기대수익) 근거

    @property
    def beats_bnh(self) -> bool:
        return self.total_return > self.bnh_return

    def summary(self) -> str:
        sl = f" · 손절 -{self.stop_loss:.0%}" if self.stop_loss else ""
        return (
            f"총수익 {self.total_return*100:+.1f}% (B&H {self.bnh_return*100:+.1f}%) · "
            f"CAGR {self.cagr*100:+.1f}% · MDD {self.mdd*100:.1f}% · "
            f"Sharpe {self.sharpe:.2f} · 승률 {self.win_rate*100:.0f}% · 거래 {self.n_trades}회"
            f"{sl}"
        )


def _trade_stats(position: pd.Series, close: pd.Series) -> tuple[float, int, float, float]:
    """진입~청산 구간별로 승률·거래수·평균 보유일·평균 수익률을 계산한다.

    평균 보유일/수익률은 매매 계획서(thesis)의 예상 회수일·기대수익 근거가 된다.
    """
    entries = position[(position == 1) & (position.shift(1, fill_value=0) == 0)].index
    exits = position[(position == 0) & (position.shift(1, fill_value=0) == 1)].index
    wins = trades = 0
    hold_days: list[int] = []
    trade_rets: list[float] = []
    for i, ent in enumerate(entries):
        # 대응 청산일(없으면 마지막 날까지 보유한 것으로 처리)
        ex = exits[i] if i < len(exits) else close.index[-1]
        ret = close.loc[ex] / close.loc[ent] - 1.0
        if ret > 0:
            wins += 1
        trades += 1
        hold_days.append(int(close.index.get_loc(ex) - close.index.get_loc(ent)))
        trade_rets.append(float(ret))
    win_rate = wins / trades if trades else 0.0
    avg_hold = float(np.mean(hold_days)) if hold_days else 0.0
    avg_ret = float(np.mean(trade_rets)) if trade_rets else 0.0
    return win_rate, trades, avg_hold, avg_ret


def run_backtest(df: pd.DataFrame, score_series: pd.Series | None = None,
                 buy_th: float | None = None, sell_th: float | None = None,
                 fee: float | None = None,
                 stop_loss: float | None = None,
                 min_hold_days: int | None = None,
                 trailing_stop: float | None = None,
                 trailing_arm: float | None = None) -> BacktestResult:
    """추세 점수 전략을 백테스트한다.

    score_series 를 주면 그걸로, 없으면 trend_score_series(df) 로 신호를 만든다.
    buy_th/sell_th/fee 미지정 시 config 기본값(BT_BUY_TH/BT_SELL_TH/FEE)을 쓴다.
    stop_loss(예 0.08) 를 주면 손절을 백테스트에도 반영한다(모의투자와 일관):
      진입가 대비 t일 종가 수익률이 -stop_loss 이하면 t+1일 강제 청산(look-ahead 유지),
      이후 새 매수신호가 나기 전까지 현금 유지.
    min_hold_days(예 2) 를 주면 진입 후 그 일수 동안 '시그널 매도'를 무시하고 보유를
      유지한다(왕복매매 축소 검증용). 손절(stop_loss)은 최소보유와 무관하게 항상 동작.
    trailing_stop(예 0.10): 진입 후 고점(종가) 대비 -trailing_stop 이탈 시 t+1일 청산.
    trailing_arm(예 0.03): 고점이 진입가×(1+arm) 이상일 때만 트레일링 활성화 —
      신규 포지션을 트레일링이 손절보다 먼저 자르는 문제 검증용. None=항상 활성(라이브 현행).
    """
    # config 기본값 적용 (단일 출처)
    buy_th = BT_BUY_TH if buy_th is None else buy_th
    sell_th = BT_SELL_TH if sell_th is None else sell_th
    fee = FEE if fee is None else fee

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

    # 2.3) 최소 보유기간 — 진입 후 min_hold_days 일 안의 '시그널 청산'은 무시(보유 연장).
    #      과거 정보(진입 시점)만 쓰므로 look-ahead 없음. 손절은 아래 2.5에서 별도 처리.
    if min_hold_days is not None and min_hold_days > 0:
        pos_vals = position.to_numpy(copy=True)
        entry_i = None
        for i in range(len(pos_vals)):
            if pos_vals[i] == 1.0:
                if entry_i is None:
                    entry_i = i
            else:
                if entry_i is not None and (i - entry_i) < min_hold_days:
                    pos_vals[i] = 1.0   # 아직 최소 보유기간 — 청산 보류
                else:
                    entry_i = None
        position = pd.Series(pos_vals, index=position.index)

    # 2.5) 손절/트레일링 반영 — t일 종가로 판정, t+1일 강제 청산 (look-ahead 유지).
    #     손절: 진입가 대비 -stop_loss 이탈. 트레일링: 고점 대비 -trailing_stop 이탈
    #     (trailing_arm 지정 시 고점이 진입가×(1+arm) 이상일 때만 활성 — 라이브와 동일 규칙 재현).
    use_stop = stop_loss is not None and stop_loss > 0
    use_trail = trailing_stop is not None and trailing_stop > 0
    if use_stop or use_trail:
        pos_vals = position.to_numpy(copy=True)
        close_vals = close.to_numpy()
        entry_price = None      # 현재 포지션의 진입가(t+1 체결가 근사=진입일 종가)
        peak = None             # 보유 중 종가 고점 (트레일링 기준)
        stopped = False         # 강제청산 상태(새 매수신호 전까지 현금 유지)
        for i in range(len(pos_vals)):
            if stopped:
                if pos_vals[i] == 1.0:
                    # target 이 여전히 보유를 원하면 강제 현금 유지, 아니면 자연 해제
                    pos_vals[i] = 0.0
                else:
                    stopped = False  # target 자체가 현금 → 청산상태 해제(다음 진입 허용)
                    entry_price = peak = None
                    continue
            if pos_vals[i] == 1.0:
                if entry_price is None:
                    entry_price = peak = close_vals[i]  # 진입일 종가를 평단 근사로
                peak = max(peak, close_vals[i])
                hit = use_stop and close_vals[i] / entry_price - 1.0 <= -stop_loss
                if not hit and use_trail:
                    armed = trailing_arm is None or peak >= entry_price * (1 + trailing_arm)
                    hit = armed and close_vals[i] / peak - 1.0 <= -trailing_stop
                if hit:  # t일 종가 판정 → 다음 날부터 청산
                    stopped = True
                    entry_price = peak = None
            else:
                entry_price = peak = None
        position = pd.Series(pos_vals, index=position.index)

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
    win_rate, n_trades, avg_hold, avg_ret = _trade_stats(position, close)
    bnh_return = float(close.iloc[-1] / close.iloc[0] - 1.0)

    return BacktestResult(
        total_return=total_return, cagr=cagr, mdd=mdd, sharpe=sharpe,
        win_rate=win_rate, n_trades=n_trades, bnh_return=bnh_return,
        equity=equity, buy_th=buy_th, sell_th=sell_th, stop_loss=stop_loss,
        avg_hold_days=avg_hold, avg_trade_return=avg_ret,
    )
