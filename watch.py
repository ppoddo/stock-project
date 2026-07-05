"""24시간 모의투자 자동운용 워커 실행 진입점.

펀드매니저식: 관심종목을 분석해 시그널대로 가상계좌를 자동 매매하고,
하루/일주일에 한 번 텔레그램으로 요약 리포트를 보낸다. (실거래 아님)

사용법:
  ./venv/bin/python watch.py --get-chat-id   # 텔레그램 chat_id 확인
  ./venv/bin/python watch.py --once          # 한 번만 운용 + 요약 (테스트)
  ./venv/bin/python watch.py                 # 무한 루프 (기본 간격으로 반복)

텔레그램 양방향 명령 (봇에게 채팅으로 전송, 본인 chat_id만 반응):
  /status /run /report /pause /resume /help
  ※ getUpdates 폴링은 봇당 1곳만 — 워커 구동 중 다른 곳에서 폴링하면 409 충돌.

환경변수(.env): TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, WATCH_INTERVAL_MIN
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

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

KST = ZoneInfo("Asia/Seoul")             # 서버(VM)가 UTC 라서 한국시 명시
REPORT_HOURS_KST = (9, 12, 15, 18, 21)   # 하루 5회 정기 리포트 시각(한국시)


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


def maybe_send_summary(account, prices, notifier, storage,
                       force_daily=False, now: datetime | None = None) -> list[str]:
    """정기(한국시 09/12/15/18/21시)·주간 요약을 발송한다(슬롯당 1회, 중복 방지).

    재시작 등으로 슬롯 시각을 지나쳤으면 가장 최근 슬롯 1회만 캐치업 발송.
    now 는 테스트 주입용(기본: 현재 한국시).
    """
    state = storage.load_profile(REPORT_KEY)
    now = now or datetime.now(KST)
    today = now.date()
    today_s = today.isoformat()
    week_s = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    sent: list[str] = []
    eq = load_equity_history(storage)  # 성과 진단(MDD·섹터집중)용 자산 시계열

    # 정기 리포트: 지나온 슬롯 중 최신 것 1회 (오늘 아직 슬롯 전이면 없음)
    passed = [h for h in REPORT_HOURS_KST if h <= now.hour]
    slot_key = f"{today_s}T{passed[-1]:02d}" if passed else None
    if force_daily or (slot_key and state.get("last_slot") != slot_key):
        label = f"{passed[-1]:02d}시" if passed else "수동"
        today_trades = [h for h in account.history if h["date"].startswith(today_s)]
        notifier.send(build_summary(account, prices, label, today_trades, equity_history=eq))
        if slot_key:
            state["last_slot"] = slot_key
        sent.append(label)

    if state.get("last_weekly") != week_s:
        monday = (today - timedelta(days=today.weekday())).isoformat()
        week_trades = [h for h in account.history if h["date"] >= monday]
        notifier.send(build_summary(account, prices, "주간", week_trades, equity_history=eq))
        state["last_weekly"] = week_s
        sent.append("주간")

    storage.save_profile(state, REPORT_KEY)
    return sent


TG_HELP = (
    "🤖 <b>모의투자 봇 명령</b>\n"
    "/status — 계좌 현황 + 성과 진단\n"
    "/run — 즉시 자동운용 1회\n"
    "/report — 일일 리포트 즉시 발송\n"
    "/pause — 자동매매 일시정지\n"
    "/resume — 자동매매 재개\n"
    "/help — 이 도움말\n"
    "⚠️ 가상계좌 전용 · 투자 판단·책임은 본인에게"
)


def watch_loop(once: bool) -> None:
    data_src = get_source("fdr")
    news_src = get_news_source("google")
    storage = get_storage("local")
    notifier = get_notifier("auto")

    account = PaperAccount.from_dict(storage.load_profile(PAPER_KEY))
    interval = int(os.getenv("WATCH_INTERVAL_MIN", "30")) * 60
    tg = notifier if isinstance(notifier, TelegramNotifier) and notifier.ready else None
    ch = "텔레그램" if tg else "콘솔(텔레그램 미설정)"
    print(f"모의투자 자동운용 시작 · 알림: {ch} · 간격: {interval//60}분 · 현금 {account.cash:,.0f}원")
    if tg and not once:
        print("텔레그램 명령 대기: /status /run /report /pause /resume /help")

    paused = False
    next_run = 0.0
    last_prices: dict[str, float] = {}
    tg_offset: int | None = None

    def run_cycle() -> None:
        nonlocal last_prices
        profile = UserProfile.from_dict(storage.load_profile())
        symbols = target_universe(profile)
        if not symbols:
            print("⚠️ 운용 대상 없음. 대시보드에서 ⭐ 즐겨찾기나 선호 테마를 등록하세요.")
            return
        ts = datetime.now().strftime("%H:%M:%S")
        trades, prices = run_paper_trading(account, profile, data_src, news_src, symbols)
        storage.save_profile(account.to_dict(), PAPER_KEY)
        record_snapshot(storage, account, prices)  # 자산 시계열 누적(그래프 분석용)
        last_prices = prices
        tv = account.total_value(prices)
        print(f"[{ts}] 운용 {len(symbols)}종목 · 체결 {len(trades)}건 · "
              f"총자산 {tv:,.0f}원 ({account.total_return(prices)*100:+.2f}%)")
        sent = maybe_send_summary(account, prices, notifier, storage, force_daily=once)
        if sent:
            print(f"        → {'/'.join(sent)} 요약 발송")

    def status_prices() -> dict[str, float]:
        """현황 표시용 가격: 마지막 사이클 시세, 없으면 평단 폴백."""
        return last_prices or {s: h.avg_price for s, h in account.holdings.items()}

    def handle_command(text: str) -> None:
        nonlocal paused, next_run
        cmd = text.split()[0].split("@")[0].lower()
        if cmd == "/status":
            tg.send(build_summary(account, status_prices(), "현황",
                                  equity_history=load_equity_history(storage)))
        elif cmd == "/run":
            tg.send("▶️ 즉시 자동운용 1회를 시작합니다…")
            next_run = 0.0
        elif cmd == "/report":
            sent = maybe_send_summary(account, status_prices(), tg, storage, force_daily=True)
            if "일일" not in sent:
                tg.send("리포트를 보냈어요.")
        elif cmd == "/pause":
            paused = True
            tg.send("⏸ 자동매매 일시정지. 리포트·명령은 계속 동작해요. /resume 으로 재개")
        elif cmd == "/resume":
            paused = False
            next_run = 0.0
            tg.send("▶️ 자동매매 재개! 바로 1회 운용합니다.")
        elif cmd in ("/help", "/start"):
            tg.send(TG_HELP)
        else:
            tg.send(f"모르는 명령이에요: {cmd}\n/help 를 참고하세요.")

    while True:
        if time.time() >= next_run:
            if paused:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏸ 일시정지 중 — 매매 건너뜀")
            else:
                run_cycle()
            if once:
                break
            next_run = time.time() + interval

        # 정기 리포트 슬롯 체크 — 사이클(30분)과 무관하게 정시 부근 발송 (일시정지 중에도)
        try:
            sent = maybe_send_summary(account, status_prices(), notifier, storage)
            if sent:
                print(f"        → {'/'.join(sent)} 리포트 발송")
        except Exception as e:  # noqa: BLE001 - 리포트 실패가 워커를 죽이지 않게
            print(f"[리포트] 발송 오류(무시하고 계속): {e}")

        # 다음 사이클까지 텔레그램 명령 수신 (장기폴링 ~20초 단위)
        if tg:
            try:
                for u in tg.get_updates(offset=tg_offset, timeout=20):
                    tg_offset = u["update_id"] + 1
                    msg = u.get("message") or {}
                    if str(msg.get("chat", {}).get("id")) != str(tg.chat_id):
                        continue  # 본인 chat_id 외 무시 (보안)
                    text = (msg.get("text") or "").strip()
                    if text.startswith("/"):
                        print(f"[TG] 명령 수신: {text}")
                        handle_command(text)
            except Exception as e:  # noqa: BLE001 - 폴링 실패가 워커를 죽이지 않게
                print(f"[TG] 폴링 오류(무시하고 계속): {e}")
                time.sleep(5)
        else:
            time.sleep(min(interval, 60))


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
