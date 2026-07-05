"""24시간 모의투자 자동운용 워커 실행 진입점.

펀드매니저식: 관심종목을 분석해 시그널대로 가상계좌를 자동 매매하고,
하루/일주일에 한 번 텔레그램으로 요약 리포트를 보낸다. (실거래 아님)

사용법:
  ./venv/bin/python watch.py --get-chat-id   # 텔레그램 chat_id 확인
  ./venv/bin/python watch.py --once          # 한 번만 운용 + 요약 (테스트)
  ./venv/bin/python watch.py                 # 무한 루프 (기본 간격으로 반복)

환경변수(.env): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WATCH_INTERVAL_MIN
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

from trading.data import get_source
from trading.news import get_news_source
from trading.storage import get_storage
from trading.notify import get_notifier, TelegramNotifier
from trading.profile import UserProfile
from trading.paper import (
    PaperAccount, run_paper_trading, target_universe, build_summary, record_snapshot,
    load_equity_history,
)

load_dotenv()

PAPER_KEY = "_paper"          # 가상계좌 저장 키
REPORT_KEY = "_report_state"  # 요약 발송 상태 키


def get_chat_id() -> None:
    """봇에게 보낸 메시지에서 chat_id 를 찾아 출력한다."""
    tg = TelegramNotifier()
    if not tg.token:
        print("❌ TELEGRAM_BOT_TOKEN 이 .env 에 없습니다.")
        return
    updates = tg.get_updates()
    if not updates:
        print("받은 메시지가 없습니다. 텔레그램에서 봇에게 아무 메시지나 먼저 보내세요.")
        return
    seen = set()
    for u in updates:
        chat = (u.get("message") or u.get("channel_post") or {}).get("chat", {})
        if chat.get("id") and chat["id"] not in seen:
            seen.add(chat["id"])
            print(f"chat_id = {chat['id']}  ({chat.get('title') or chat.get('first_name','')})")
    print("\n→ 위 chat_id 를 .env 의 TELEGRAM_CHAT_ID 에 넣으세요.")


def maybe_send_summary(account, prices, notifier, storage, force_daily=False) -> list[str]:
    """날짜/주차가 바뀌면 일일·주간 요약을 발송한다(중복 방지)."""
    state = storage.load_profile(REPORT_KEY)
    today = date.today()
    today_s = today.isoformat()
    week_s = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    sent: list[str] = []
    eq = load_equity_history(storage)  # 성과 진단(MDD·섹터집중)용 자산 시계열

    if force_daily or state.get("last_daily") != today_s:
        today_trades = [h for h in account.history if h["date"].startswith(today_s)]
        notifier.send(build_summary(account, prices, "일일", today_trades, equity_history=eq))
        state["last_daily"] = today_s
        sent.append("일일")

    if state.get("last_weekly") != week_s:
        monday = (today - timedelta(days=today.weekday())).isoformat()
        week_trades = [h for h in account.history if h["date"] >= monday]
        notifier.send(build_summary(account, prices, "주간", week_trades, equity_history=eq))
        state["last_weekly"] = week_s
        sent.append("주간")

    storage.save_profile(state, REPORT_KEY)
    return sent


def watch_loop(once: bool) -> None:
    data_src = get_source("fdr")
    news_src = get_news_source("google")
    storage = get_storage("local")
    notifier = get_notifier("auto")

    account = PaperAccount.from_dict(storage.load_profile(PAPER_KEY))
    interval = int(os.getenv("WATCH_INTERVAL_MIN", "30")) * 60
    ch = "텔레그램" if notifier.__class__.__name__ == "TelegramNotifier" else "콘솔(텔레그램 미설정)"
    print(f"모의투자 자동운용 시작 · 알림: {ch} · 간격: {interval//60}분 · 현금 {account.cash:,.0f}원")

    while True:
        profile = UserProfile.from_dict(storage.load_profile())
        symbols = target_universe(profile)
        if not symbols:
            print("⚠️ 운용 대상 없음. 대시보드에서 ⭐ 즐겨찾기나 선호 테마를 등록하세요.")
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            trades, prices = run_paper_trading(account, profile, data_src, news_src, symbols)
            storage.save_profile(account.to_dict(), PAPER_KEY)
            record_snapshot(storage, account, prices)  # 자산 시계열 누적(그래프 분석용)
            tv = account.total_value(prices)
            print(f"[{ts}] 운용 {len(symbols)}종목 · 체결 {len(trades)}건 · "
                  f"총자산 {tv:,.0f}원 ({account.total_return(prices)*100:+.2f}%)")
            sent = maybe_send_summary(account, prices, notifier, storage, force_daily=once)
            if sent:
                print(f"        → {'/'.join(sent)} 요약 발송")
        if once:
            break
        time.sleep(interval)


def main() -> None:
    ap = argparse.ArgumentParser(description="24시간 모의투자 자동운용 워커")
    ap.add_argument("--get-chat-id", action="store_true", help="텔레그램 chat_id 확인")
    ap.add_argument("--once", action="store_true", help="한 번만 운용 + 요약 발송")
    args = ap.parse_args()

    if args.get_chat_id:
        get_chat_id()
    else:
        watch_loop(once=args.once)


if __name__ == "__main__":
    main()
