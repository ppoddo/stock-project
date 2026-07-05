"""WP3 그리드서치 실행 스크립트.

운용 유니버스(현재 프로필의 즐겨찾기 ∪ 선호 테마 대표종목, 없으면 폴백)를
최근 3년 백테스트로 (buy_th, sell_th, stop_loss) 그리드서치 하고,
- 종목 평균 지표 순위 표 + 종목별 표를 docs/tuning-result.md 로 저장,
- 원자료를 data_store/_gridsearch.json 으로 저장,
- 최적 조합을 콘솔에 출력한다(config 갱신 근거).

실행: ./venv/bin/python scripts/run_gridsearch.py
      (인자로 종목코드를 넘기면 그 종목들로 유니버스 대체)

⚠️ 백테스트 전용 — 실거래 아님. DataSource 경유(FinanceDataReader 직접 import 금지).
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# 저장소 루트를 import 경로에 추가 (scripts/ 에서 직접 실행 대비)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from trading.backtest.gridsearch import (  # noqa: E402
    BUY_GRID, SELL_GRID, STOP_GRID, MDD_FILTER, run_grid, select_best, rank_key,
)
from trading.data import get_source  # noqa: E402
from trading.profile.profile import UserProfile  # noqa: E402
from trading.paper.trader import target_universe  # noqa: E402
from trading.storage import get_storage  # noqa: E402

START = "2023-01-01"
DOC_PATH = ROOT / "docs" / "tuning-result.md"
RAW_PATH = ROOT / "data_store" / "_gridsearch.json"

# 프로필이 비었을 때 폴백 유니버스 (반도체 대표 한/미)
FALLBACK_UNIVERSE = [
    "005930", "000660", "042700",          # 삼성전자, SK하이닉스, 한미반도체
    "NVDA", "AMD", "TSM", "AVGO", "MU",     # 미국 반도체 대표
]


def _resolve_universe(argv: list[str]) -> list[str]:
    """CLI 인자 > 현재 프로필 유니버스 > 폴백 순으로 운용 종목을 정한다."""
    if argv:
        return argv
    try:
        profile = UserProfile.from_dict(get_storage("local").load_profile())
        uni = target_universe(profile)
        if uni:
            return uni
    except Exception:  # noqa: BLE001 — 프로필 로드 실패 시 폴백
        pass
    return FALLBACK_UNIVERSE


def _fmt_pct(x: float) -> str:
    return f"{x * 100:+.1f}%"


def _write_doc(ranked: list, best, relaxed: bool, universe: list[str],
               name_of) -> None:
    """상위 조합 표 + 최적 조합 종목별 표 + 채택 근거를 md 로 쓴다."""
    lines: list[str] = []
    lines.append("# 전략 튜닝 결과 — 그리드서치 (WP3)")
    lines.append("")
    lines.append(f"> 생성: {date.today().isoformat()} · 기간 {START}~현재 · "
                 f"유니버스 {len(universe)}종목 · 조합 {len(ranked)}개")
    lines.append(">")
    lines.append("> 백테스트는 **추세 점수(0~100)** 단일 신호 기준이다. "
                 "매수≥buy_th·매도≤sell_th 로 보유/현금을 결정하고, "
                 "손절률은 진입가 대비 손실 한도(초과 시 다음날 강제 청산)다.")
    lines.append("> \"느낌\"이 아니라 CAGR·MDD·Sharpe·승률 수치로 최적값을 고른다(안전규칙 4).")
    lines.append("")

    lines.append("## 유니버스")
    lines.append("")
    lines.append(", ".join(f"{s}({name_of(s)})" for s in universe))
    lines.append("")

    # 상위 조합 표
    lines.append("## 상위 조합 (Sharpe↓ · MDD 얕음 · CAGR↓ 순)")
    lines.append("")
    lines.append("| 순위 | 매수≥ | 매도≤ | 손절 | 평균 CAGR | 평균 MDD | 평균 Sharpe | 평균 승률 | B&H우위 | 종목수 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(ranked[:10], 1):
        sl = "없음" if r.stop_loss is None else f"-{r.stop_loss:.0%}"
        mark = " ⭐" if r is best else ""
        lines.append(
            f"| {i}{mark} | {r.buy_th:g} | {r.sell_th:g} | {sl} | "
            f"{_fmt_pct(r.avg_cagr)} | {r.avg_mdd*100:.1f}% | {r.avg_sharpe:.2f} | "
            f"{r.avg_win_rate*100:.0f}% | {r.avg_beats_bnh*100:.0f}% | {r.n_symbols} |"
        )
    lines.append("")

    # 최적 조합 종목별 표
    if best is not None:
        lines.append(f"## 채택 조합 종목별 상세 — {best.label}")
        lines.append("")
        lines.append("| 종목 | 이름 | CAGR | MDD | Sharpe | 승률 | B&H우위 |")
        lines.append("|---|---|---|---|---|---|---|")
        for s, (cagr, mdd, sharpe, win, beats) in best.per_symbol.items():
            lines.append(
                f"| {s} | {name_of(s)} | {_fmt_pct(cagr)} | {mdd*100:.1f}% | "
                f"{sharpe:.2f} | {win*100:.0f}% | {'○' if beats else '×'} |"
            )
        lines.append("")

    # 채택 근거
    lines.append("## 채택 근거")
    lines.append("")
    if best is not None:
        lines.append(f"- **채택: {best.label}** — "
                     f"평균 Sharpe {best.avg_sharpe:.2f}, 평균 MDD {best.avg_mdd*100:.1f}%, "
                     f"평균 CAGR {_fmt_pct(best.avg_cagr)}, 평균 승률 {best.avg_win_rate*100:.0f}%.")
        lines.append(f"- 랭킹 기준: 위험조정수익(Sharpe) 우선 → 낙폭(MDD) 얕은 순 → CAGR 순.")
        if relaxed:
            lines.append(f"- ⚠️ MDD {MDD_FILTER*100:.0f}% 필터를 통과한 조합이 없어 **필터를 완화**해 재선정했다. "
                         f"유니버스/기간에 따라 낙폭이 큰 구간이 있으니 실운용은 보수적으로 볼 것.")
        else:
            lines.append(f"- MDD 필터({MDD_FILTER*100:.0f}% 이내) 통과 조합 중에서 선정 — "
                         f"마스터 플랜의 \"MDD 크다\" 문제를 정면 대응.")
    lines.append("")
    lines.append("## config 반영")
    lines.append("")
    if best is not None:
        lines.append(f"- `trading/config.py`: `BT_BUY_TH = {best.buy_th:g}`, "
                     f"`BT_SELL_TH = {best.sell_th:g}` (채택 조합의 임계값).")
        lines.append("- **손절률 STOP_LOSS_PCT 는 0.08(-8%) 유지**: 무손절 조합이 Sharpe 로 근소하게 앞서더라도, "
                     "위험조정수익 차이가 무시할 수준이면 낙폭(MDD)이 얕은 손절 조합을 택한다. "
                     "이는 WP2 손절 도입 취지와 안전규칙 4(MDD 중시)에 부합한다 "
                     "— 표의 무손절/-8% 행을 나란히 비교해 판단.")
    lines.append("- ⚠️ 종합점수 임계값(`BUY_THRESHOLD`/`SELL_THRESHOLD`)은 **직접 대입 금지**. "
                 "백테스트는 추세 점수(단일), 실운용은 추세·뉴스·선호 가중합(스케일이 다름)이다. "
                 "종합 임계값은 위 추세 최적선을 참고해 보수적으로 잠정 유지하고, 실운용 데이터로 미세조정한다.")
    lines.append("")

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_raw(ranked: list, best, relaxed: bool, universe: list[str]) -> None:
    payload = {
        "generated": date.today().isoformat(),
        "start": START,
        "universe": universe,
        "grid": {"buy": BUY_GRID, "sell": SELL_GRID,
                 "stop": [s for s in STOP_GRID]},
        "mdd_filter": MDD_FILTER,
        "filter_relaxed": relaxed,
        "best": None if best is None else {
            "buy_th": best.buy_th, "sell_th": best.sell_th, "stop_loss": best.stop_loss,
            "avg_cagr": best.avg_cagr, "avg_mdd": best.avg_mdd,
            "avg_sharpe": best.avg_sharpe, "avg_win_rate": best.avg_win_rate,
            "avg_beats_bnh": best.avg_beats_bnh,
        },
        "results": [
            {
                "buy_th": r.buy_th, "sell_th": r.sell_th, "stop_loss": r.stop_loss,
                "avg_cagr": r.avg_cagr, "avg_mdd": r.avg_mdd,
                "avg_sharpe": r.avg_sharpe, "avg_win_rate": r.avg_win_rate,
                "avg_beats_bnh": r.avg_beats_bnh, "n_symbols": r.n_symbols,
            }
            for r in ranked
        ],
    }
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    universe = _resolve_universe(sys.argv[1:])
    source = get_source("fdr")

    def name_of(s: str) -> str:
        try:
            return source.get_name(s)
        except Exception:  # noqa: BLE001
            return s

    print(f"[gridsearch] 유니버스 {len(universe)}종목 · 기간 {START}~ · "
          f"그리드 {len(BUY_GRID)}×{len(SELL_GRID)}×{len(STOP_GRID)} 실행 중...")
    results = run_grid(universe, source, start=START)
    if not results:
        print("[gridsearch] 결과 없음 — 데이터 로드 실패(네트워크/종목 확인).")
        return

    ranked = sorted(results, key=rank_key)
    best, relaxed = select_best(results)

    _write_doc(ranked, best, relaxed, universe, name_of)
    _write_raw(ranked, best, relaxed, universe)

    print(f"[gridsearch] 완료 · 조합 {len(results)}개 · 문서 {DOC_PATH}")
    if best is not None:
        sl = "없음" if best.stop_loss is None else f"-{best.stop_loss:.0%}"
        print(f"[gridsearch] BEST → 매수≥{best.buy_th:g} · 매도≤{best.sell_th:g} · 손절 {sl} "
              f"| Sharpe {best.avg_sharpe:.2f} · MDD {best.avg_mdd*100:.1f}% · "
              f"CAGR {best.avg_cagr*100:+.1f}% · 승률 {best.avg_win_rate*100:.0f}%"
              + ("  (MDD 필터 완화됨)" if relaxed else ""))
        print("[gridsearch] config 갱신: BT_BUY_TH / BT_SELL_TH / STOP_LOSS_PCT "
              "(종합 임계값은 직접 대입 금지 — docs/tuning-result.md 참고)")


if __name__ == "__main__":
    main()
