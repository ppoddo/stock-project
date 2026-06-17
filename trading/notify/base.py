"""알림 채널 추상 인터페이스.

데이터·뉴스·저장소와 동일하게 알림도 추상화한다.
지금은 텔레그램/콘솔, 나중에 이메일·디스코드 등으로 확장해도 워커 코드는 그대로.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    """알림 발송 공통 인터페이스."""

    @abstractmethod
    def send(self, message: str) -> bool:
        """메시지를 발송한다. 성공하면 True."""
        raise NotImplementedError

    @property
    @abstractmethod
    def ready(self) -> bool:
        """발송 가능한 상태인지(키 설정 등). False면 워커가 콘솔로 대체."""
        raise NotImplementedError
