"""저장소 추상 인터페이스.

프로필을 dict(JSON 직렬화 가능 형태)로 주고받는다.
구현체는 이 dict 를 로컬 파일/Firestore/Postgres 등 원하는 곳에 저장하면 된다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class Storage(ABC):
    """사용자 데이터 저장/조회 공통 인터페이스."""

    @abstractmethod
    def load_profile(self, user_id: str = "default") -> dict:
        """사용자 프로필 dict 를 반환한다. 없으면 빈 dict."""
        raise NotImplementedError

    @abstractmethod
    def save_profile(self, data: dict, user_id: str = "default") -> None:
        """사용자 프로필 dict 를 저장한다."""
        raise NotImplementedError
