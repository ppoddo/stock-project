"""알림 모듈.

get_notifier() 로 알림 채널을 받는다. 텔레그램이 준비 안 됐으면 콘솔로 대체.
"""
from .base import Notifier
from .telegram import TelegramNotifier
from .console import ConsoleNotifier


def get_notifier(name: str = "auto") -> Notifier:
    """알림 채널 구현체를 반환한다.

    'auto': 텔레그램 토큰이 있으면 텔레그램, 없으면 콘솔.
    'telegram' / 'console': 명시적 선택.
    """
    if name == "console":
        return ConsoleNotifier()
    if name in ("telegram", "auto"):
        tg = TelegramNotifier()
        if tg.ready:
            return tg
        if name == "telegram":
            return tg  # 준비 안 됐어도 명시 요청이면 그대로(이유 노출)
        return ConsoleNotifier()  # auto 인데 준비 안 됨 → 콘솔
    raise ValueError(f"알 수 없는 알림 채널: {name}")


__all__ = ["Notifier", "TelegramNotifier", "ConsoleNotifier", "get_notifier"]
