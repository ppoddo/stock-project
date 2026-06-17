"""콘솔 알림 구현.

텔레그램 토큰이 없을 때의 대체(fallback). 터미널에 알림을 출력한다.
개발/테스트나 토큰 발급 전에 워커 동작을 확인할 때 쓴다.
"""
from __future__ import annotations

from datetime import datetime

from .base import Notifier


class ConsoleNotifier(Notifier):
    """알림을 표준출력에 찍는다. 항상 ready=True."""

    @property
    def ready(self) -> bool:
        return True

    def send(self, message: str) -> bool:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[🔔 알림 {ts}]\n{message}\n" + "-" * 40)
        return True
