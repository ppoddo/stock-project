"""24시간 감시 워커 실행 진입점.

사용법:
  ./venv/bin/python watch.py --get-chat-id   # 텔레그램 chat_id 확인
  ./venv/bin/python watch.py --once          # 한 번만 점검 (테스트)
  ./venv/bin/python watch.py                 # 무한 루프 (기본 간격으로 반복)

환경변수(.env): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WATCH_INTERVAL_MIN
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv

from trading.data import get_source
from trading.news import get_news_source
from trading.storage import get_storage
from trading.notify import get_notifier, TelegramNotifier
from trading.profile import UserProfile
from trading.monitor import run_watch

load_dotenv()


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


def watch_loop(once: bool) -> None:
    data_src = get_source("fdr")
    news_src = get_news_source("google")
    storage = get_storage("local")
    notifier = get_notifier("auto")

    profile = UserProfile.from_dict(storage.load_profile())
    interval = int(os.getenv("WATCH_INTERVAL_MIN", "30")) * 60

    ch = "텔레그램" if notifier.ready and notifier.__class__.__name__ == "TelegramNotifier" else "콘솔(텔레그램 미설정)"
    print(f"감시 시작 · 알림채널: {ch} · 간격: {interval//60}분")

    while True:
        symbols = sorted(set(profile.favorites))  # 즐겨찾기를 관심종목으로
        if not symbols:
            print("⚠️ 즐겨찾기 종목이 없습니다. 대시보드에서 ⭐ 등록 후 다시 실행하세요.")
        else:
            ts = datetime.now().strftime("%H:%M:%S")
            report = run_watch(symbols, profile, data_src, news_src, notifier, storage)
            print(f"[{ts}] 점검 {len(report.checked)} · 알림 {len(report.alerted)}"
                  + (f" {report.alerted}" if report.alerted else "")
                  + (f" · 오류 {report.errors}" if report.errors else ""))
        if once:
            break
        time.sleep(interval)
        profile = UserProfile.from_dict(storage.load_profile())  # 매 주기 프로필 갱신


def main() -> None:
    ap = argparse.ArgumentParser(description="24시간 시그널 감시 워커")
    ap.add_argument("--get-chat-id", action="store_true", help="텔레그램 chat_id 확인")
    ap.add_argument("--once", action="store_true", help="한 번만 점검하고 종료")
    args = ap.parse_args()

    if args.get_chat_id:
        get_chat_id()
    else:
        watch_loop(once=args.once)


if __name__ == "__main__":
    main()
