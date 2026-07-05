"""텔레그램 봇 알림 구현.

준비물 (사용자가 직접):
  1. 텔레그램에서 @BotFather → /newbot → 봇 토큰 발급
  2. 만든 봇과 대화 시작(아무 메시지나 전송)
  3. chat_id 확인: watch.py --get-chat-id  (또는 getUpdates API)
  4. .env 에 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 입력
"""
from __future__ import annotations

import os

import requests

from .base import Notifier

_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier(Notifier):
    """텔레그램 Bot API 로 메시지를 보낸다."""

    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")

    @property
    def ready(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, message: str) -> bool:
        if not self.ready:
            return False
        url = _API.format(token=self.token, method="sendMessage")
        try:
            r = requests.post(url, timeout=10, data={
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
            return r.status_code == 200
        except requests.RequestException:
            return False

    def get_updates(self, offset: int | None = None, timeout: int = 0) -> list[dict]:
        """수신 메시지 목록. offset 이후만, timeout>0 이면 장기폴링(명령 수신용).

        offset 미지정 호출(chat_id 확인용)은 읽음 확정을 하지 않아 안전하다.
        ※ getUpdates 는 봇당 동시 1곳만 폴링 가능 — 워커(VM) 구동 중 로컬에서 또 돌리면 409.
        """
        if not self.token:
            return []
        url = _API.format(token=self.token, method="getUpdates")
        params: dict = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        try:
            r = requests.get(url, params=params, timeout=timeout + 10)
            return r.json().get("result", []) if r.status_code == 200 else []
        except requests.RequestException:
            return []
