"""저장소 모듈.

사용자 프로필 등을 저장/조회한다. 데이터·뉴스 소스와 동일하게 추상화해,
지금은 로컬 JSON으로 쓰다가 배포 시 Firebase/Supabase 구현으로 교체할 수 있다.
"""
from .base import Storage
from .local import LocalStorage


def get_storage(name: str = "local") -> Storage:
    """이름으로 저장소 구현체를 반환한다."""
    backends = {
        "local": LocalStorage,
        # 배포 시 추가 예정: "firebase": FirebaseStorage, "supabase": SupabaseStorage
    }
    if name not in backends:
        raise ValueError(f"알 수 없는 저장소: {name} (가능: {list(backends)})")
    return backends[name]()


__all__ = ["Storage", "LocalStorage", "get_storage"]
