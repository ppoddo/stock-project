"""매매 계획서(thesis) — 평가·회수예측·리뷰 (2026-07-08 사용자 설계).

매수 시점에 "왜 사는지 + 언제/얼마에 회수할 계획인지"를 데이터로 기록하고,
청산 시점에 계획 대비 실제를 자동 채점한다. 이 기록이 쌓여 알고리즘 자체 평가(/retro)의
원천 데이터가 된다.

계획의 근거는 그 종목의 백테스트 통계(평균 보유일·평균 거래수익)다 — 느낌이 아니라 숫자.
⚠️ 가상계좌 전용. 예측은 참고용이며 투자 판단·책임은 사용자 본인.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

from ..config import STOP_LOSS_PCT
from ..analysis import trend_score_series
from ..backtest import run_backtest


def build_thesis(df, price_krw: float, scores: dict, today_iso: str | None = None) -> dict:
    """매수 계획서를 만든다.

    df: 해당 종목 가격 데이터프레임(분석 시 이미 확보된 것 재사용 — 추가 조회 없음)
    price_krw: 매수가(원화 환산), scores: {'trend','news','pref','total'}
    반환 dict 는 JSON 직렬화 가능해야 한다(가상계좌 저장 포맷).
    """
    today = today_iso or datetime.now().date().isoformat()
    bt = run_backtest(df, score_series=trend_score_series(df), stop_loss=STOP_LOSS_PCT)

    # 예상 회수일: 이 종목 전략의 평균 보유 영업일 (최소 1일)
    hold_bdays = max(int(round(bt.avg_hold_days)), 1)
    expected_exit = str(np.busday_offset(today, hold_bdays, roll="forward"))

    return {
        "planned_at": today,
        "entry_price": round(float(price_krw), 2),
        "scores": {k: round(float(v), 1) for k, v in scores.items()},
        "expected_hold_bdays": hold_bdays,                       # 평가단계 회수시점 예측
        "expected_exit_date": expected_exit,
        "expected_return_pct": round(bt.avg_trade_return * 100, 1),  # 백테스트 평균 거래수익
        "target_price": round(float(price_krw) * (1 + bt.avg_trade_return), 2),
        "stop_price": round(float(price_krw) * (1 - STOP_LOSS_PCT), 2),
        "bt_win_rate": round(bt.win_rate * 100, 0),              # 계획 신뢰도 참고치
        "bt_n_trades": bt.n_trades,
    }


def review_exit(thesis: dict | None, sell_price: float, sell_reason: str,
                today_iso: str | None = None) -> dict | None:
    """청산 시 계획 대비 실제를 채점한다. 계획서 없으면(구 데이터) None."""
    if not thesis:
        return None
    today = today_iso or datetime.now().date().isoformat()
    actual_bdays = int(np.busday_count(thesis["planned_at"], today))
    actual_ret = (sell_price / thesis["entry_price"] - 1.0) * 100 if thesis["entry_price"] else 0.0
    expected_bdays = thesis.get("expected_hold_bdays", 0)

    # 보유기간 판정: 예상 대비 절반 미만=조기, 1.5배 초과=지연, 그 사이=계획범위
    if expected_bdays <= 0:
        timing = "기준없음"
    elif actual_bdays < expected_bdays * 0.5:
        timing = "조기회수"
    elif actual_bdays > expected_bdays * 1.5:
        timing = "지연회수"
    else:
        timing = "계획범위"

    hit = actual_ret >= thesis.get("expected_return_pct", 0)
    return {
        "reviewed_at": today,
        "actual_hold_bdays": actual_bdays,
        "expected_hold_bdays": expected_bdays,
        "actual_return_pct": round(actual_ret, 1),
        "expected_return_pct": thesis.get("expected_return_pct"),
        "timing": timing,                 # 조기회수/계획범위/지연회수
        "return_hit": bool(hit),          # 기대수익 달성 여부
        "sell_reason": sell_reason,
        "verdict": f"{timing} · 기대수익 {'달성' if hit else '미달'}",
    }
