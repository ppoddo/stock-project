"""모의투자 자산 저널 (시계열 데이터 수집).

매 운용 시점의 총자산·수익률·현금 등을 '하루 1개 레코드'로 누적 저장한다.
→ 나중에 자산곡선·수익률 추이 등 그래프 분석의 원천 데이터가 된다.
거래내역(account.history)과 별개로, 평가금액의 시계열을 남기는 게 목적.
"""
from __future__ import annotations

from datetime import date

from ..storage.base import Storage
from .account import PaperAccount

EQUITY_KEY = "_equity"  # 자산 시계열 저장 키


def record_snapshot(storage: Storage, account: PaperAccount,
                    prices: dict[str, float], key: str = EQUITY_KEY) -> dict:
    """현재 계좌 상태를 일별 스냅샷으로 기록한다(같은 날이면 마지막 값으로 갱신)."""
    data = storage.load_profile(key)
    history: list[dict] = data.get("history", [])
    today = date.today().isoformat()
    snap = {
        "date": today,
        "total": round(account.total_value(prices)),
        "cash": round(account.cash),
        "holdings_value": round(account.market_value(prices)),
        "return_pct": round(account.total_return(prices) * 100, 2),
        "n_holdings": len(account.holdings),
    }
    if history and history[-1]["date"] == today:
        history[-1] = snap          # 같은 날: 최신값으로 덮어쓰기
    else:
        history.append(snap)        # 새로운 날: 추가
    storage.save_profile({"history": history}, key)
    return snap


def load_equity_history(storage: Storage, key: str = EQUITY_KEY) -> list[dict]:
    """누적된 자산 시계열을 반환한다."""
    return storage.load_profile(key).get("history", [])
