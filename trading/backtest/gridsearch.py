"""임계값·손절률 그리드서치 (WP3).

운용 유니버스 전 종목 × 최근 N년으로 (buy_th, sell_th, stop_loss) 조합을 백테스트하고
종목 평균 지표로 순위를 매긴다. "느낌"이 아니라 CAGR/MDD/Sharpe/승률 수치로 최적값을 고른다.

⚠️ DataSource 경유(FinanceDataReader 직접 import 금지). 백테스트·모의투자 전용(실거래 아님).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..data.base import DataSource
from .engine import run_backtest

# 그리드 (조합 수 억제: 4 × 4 × 3 = 48, 매도선<매수선 제약으로 실제로는 더 적음)
BUY_GRID = [55, 60, 65, 70]
SELL_GRID = [35, 40, 45, 50]
STOP_GRID: list[float | None] = [None, 0.08, 0.12]

# MDD 필터 — 이보다 깊은 낙폭 조합은 채택 후보에서 제외(마스터 플랜: "MDD 크다" 대응)
MDD_FILTER = -0.35


@dataclass
class GridResult:
    """한 (buy_th, sell_th, stop_loss) 조합의 종목 평균 성과."""

    buy_th: float
    sell_th: float
    stop_loss: float | None
    avg_cagr: float
    avg_mdd: float
    avg_sharpe: float
    avg_win_rate: float
    avg_beats_bnh: float                 # B&H 를 이긴 종목 비율
    n_symbols: int                       # 집계에 쓰인 종목 수
    per_symbol: dict = field(default_factory=dict)   # symbol -> (cagr, mdd, sharpe, win_rate, beats_bnh)

    @property
    def label(self) -> str:
        sl = "없음" if self.stop_loss is None else f"-{self.stop_loss:.0%}"
        return f"매수≥{self.buy_th:g}·매도≤{self.sell_th:g}·손절 {sl}"


def _aggregate(buy_th: float, sell_th: float, stop_loss: float | None,
               per: dict) -> GridResult:
    """종목별 결과 dict 를 평균 지표로 집계한다."""
    n = len(per)
    if n == 0:
        return GridResult(buy_th, sell_th, stop_loss, 0.0, 0.0, 0.0, 0.0, 0.0, 0, {})
    cagrs = [v[0] for v in per.values()]
    mdds = [v[1] for v in per.values()]
    sharpes = [v[2] for v in per.values()]
    wins = [v[3] for v in per.values()]
    beats = [1.0 if v[4] else 0.0 for v in per.values()]
    return GridResult(
        buy_th=buy_th, sell_th=sell_th, stop_loss=stop_loss,
        avg_cagr=sum(cagrs) / n,
        avg_mdd=sum(mdds) / n,
        avg_sharpe=sum(sharpes) / n,
        avg_win_rate=sum(wins) / n,
        avg_beats_bnh=sum(beats) / n,
        n_symbols=n,
        per_symbol=per,
    )


def run_grid(symbols: list[str], data_source: DataSource,
             start: str = "2023-01-01",
             buy_grid: list[float] | None = None,
             sell_grid: list[float] | None = None,
             stop_grid: list[float | None] | None = None) -> list[GridResult]:
    """유니버스 각 종목의 가격을 1회 로드(캐시)하고 모든 조합을 백테스트한다.

    - 가격은 종목당 한 번만 로드(조합마다 재로드 금지 — 속도).
    - 매도선 >= 매수선 조합은 무의미하므로 스킵.
    - 로드 실패 종목은 조용히 제외.
    """
    buy_grid = BUY_GRID if buy_grid is None else buy_grid
    sell_grid = SELL_GRID if sell_grid is None else sell_grid
    stop_grid = STOP_GRID if stop_grid is None else stop_grid

    # 1) 종목별 가격 df 를 한 번만 로드 (조합마다 재로드 금지)
    price_cache: dict[str, "any"] = {}
    for s in symbols:
        try:
            price_cache[s] = data_source.get_price(s, start=start).df
        except Exception:  # noqa: BLE001 — 데이터 없는 종목은 스킵
            continue

    results: list[GridResult] = []
    for b in buy_grid:
        for sl in sell_grid:
            if sl >= b:                 # 매도선 >= 매수선 → 무의미
                continue
            for st in stop_grid:
                per: dict = {}
                for s, df in price_cache.items():
                    try:
                        r = run_backtest(df, buy_th=b, sell_th=sl, stop_loss=st)
                    except Exception:  # noqa: BLE001 — 개별 종목 백테스트 실패는 스킵
                        continue
                    per[s] = (r.cagr, r.mdd, r.sharpe, r.win_rate, r.beats_bnh)
                if per:
                    results.append(_aggregate(b, sl, st, per))
    return results


def rank_key(r: GridResult):
    """랭킹 키: Sharpe 내림 → MDD 얕음(큰 값) → CAGR 내림."""
    return (-r.avg_sharpe, r.avg_mdd, -r.avg_cagr)


def select_best(results: list[GridResult],
                mdd_filter: float = MDD_FILTER) -> tuple[GridResult | None, bool]:
    """MDD 필터를 통과한 조합 중 최적을 고른다.

    반환: (최적 조합, 필터_완화_여부). 통과 조합이 없으면 필터를 풀고 재선정(True).
    """
    if not results:
        return None, False
    filtered = [r for r in results if r.avg_mdd >= mdd_filter]
    if filtered:
        return sorted(filtered, key=rank_key)[0], False
    # 필터를 통과한 조합이 없으면 완화 후 재선정
    return sorted(results, key=rank_key)[0], True
