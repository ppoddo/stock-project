"""모의투자 요약 리포트 (일일/주간).

가상계좌의 보유종목·수익률을 텔레그램 HTML 메시지로 만든다.
"""
from __future__ import annotations

from datetime import datetime

from .account import PaperAccount
from .analytics import name_of


def build_summary(account: PaperAccount, prices: dict[str, float],
                  period: str = "일일", recent_trades: list[dict] | None = None,
                  equity_history: list[dict] | None = None) -> str:
    """보유 현황 + 수익률 요약 메시지를 만든다.

    equity_history 를 넘기면 성과 진단 한 줄(섹터 집중·최대 손실 등)을 함께 표기한다.
    미전달 시 기존과 동일하게 동작(진단 줄 생략).
    """
    total = account.total_value(prices)
    ret = account.total_return(prices)
    sign = "🔺" if ret >= 0 else "🔻"
    today = datetime.now().strftime("%Y-%m-%d")

    lines = [
        f"📊 <b>모의투자 {period} 리포트</b> ({today})",
        f"총자산 <b>{total:,.0f}원</b>  {sign} {ret*100:+.2f}%",
        f"현금 {account.cash:,.0f}원 · 보유 {len(account.holdings)}종목",
    ]

    # 성과 진단 한 줄 — 섹터 집중 경고 우선, 없으면 최대 손실 종목 (equity_history 전달 시)
    if equity_history is not None or account.holdings:
        from .analytics import analyze_performance  # 순환 import 방지 지역 import
        perf = analyze_performance(account, prices, equity_history)
        diag = next((r for r in perf.reasons if r.startswith("⚠️")), None)
        if diag is None and perf.worst is not None and perf.worst.pnl < 0:
            diag = (f"최대 손실 {perf.worst.name} "
                    f"{perf.worst.pnl_pct*100:+.1f}% ({perf.worst.pnl:,.0f}원)")
        if diag:
            lines.append(f"🩺 {diag}")

    if account.holdings:
        lines.append("\n<b>보유 종목</b>")
        for sym, h in account.holdings.items():
            px = prices.get(sym, h.avg_price)
            pnl, pnl_pct = account.position_pnl(sym, px)
            mark = "🔺" if pnl >= 0 else "🔻"
            name = name_of(account, sym)  # history 역순에서 종목명 보강
            lines.append(f"· {name} {h.shares}주 · 평단 {h.avg_price:,.0f} "
                         f"→ {px:,.0f}  {mark}{pnl_pct*100:+.1f}%")

    if recent_trades:
        lines.append(f"\n<b>최근 체결 {len(recent_trades)}건</b>")
        for t in recent_trades[-5:]:
            emoji = "🟢" if t["action"] == "매수" else "🔴"
            extra = f" (손익 {t['pnl']:+,.0f})" if "pnl" in t else ""
            lines.append(f"{emoji} {t.get('name') or t['symbol']} "
                         f"{t['shares']}주 @ {t['price']:,.0f}{extra}")

    lines.append("\n<i>⚠️ 가상계좌 시뮬레이션 · 실거래 아님 · 투자 책임은 본인</i>")
    return "\n".join(lines)
