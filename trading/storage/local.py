"""로컬 JSON 파일 기반 저장소.

사용자별로 data_store/{user_id}.json 에 저장한다. 제로 설정·즉시 작동.
배포(휘발성 파일시스템) 전까지의 개발/개인용 기본 저장소.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import Storage

# 프로젝트 루트의 data_store/ 아래에 저장 (.gitignore 의 data_cache 와 별개로 명시)
_DIR = Path(__file__).resolve().parents[2] / "data_store"


class LocalStorage(Storage):
    """JSON 파일에 프로필을 저장하는 기본 구현."""

    def __init__(self, base_dir: Path | None = None):
        self.dir = base_dir or _DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, user_id: str) -> Path:
        # 경로 조작 방지: 파일명에 쓸 수 없는 문자는 제거
        safe = "".join(c for c in user_id if c.isalnum() or c in ("-", "_")) or "default"
        return self.dir / f"{safe}.json"

    def load_profile(self, user_id: str = "default") -> dict:
        path = self._path(user_id)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save_profile(self, data: dict, user_id: str = "default") -> None:
        path = self._path(user_id)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
