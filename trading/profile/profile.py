"""사용자 프로필 + 선호도 점수 (요구사항 ③).

프로필 = 선호 테마별 가중치(0~100) + 즐겨찾기 종목.
preference_score() 로 "이 종목이 내 취향에 얼마나 맞는가"를 0~100 으로 매긴다.
이 점수는 4단계 시그널에서 트렌드·뉴스 점수와 합쳐진다.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .themes import symbol_themes


@dataclass
class UserProfile:
    """사용자의 투자 취향."""

    # 선호 테마 -> 가중치(0~100). 클수록 더 선호.
    theme_weights: dict[str, int] = field(default_factory=dict)
    # 즐겨찾기 종목코드
    favorites: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"theme_weights": self.theme_weights, "favorites": self.favorites}

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        return cls(
            theme_weights={k: int(v) for k, v in data.get("theme_weights", {}).items()},
            favorites=list(data.get("favorites", [])),
        )

    def is_favorite(self, symbol: str) -> bool:
        return symbol in self.favorites


@dataclass
class PreferenceResult:
    """선호도 분석 결과."""

    score: float           # 0~100 선호도 점수 (50=중립)
    reasons: list[str]
    matched_themes: list[str]

    @property
    def label(self) -> str:
        if self.score >= 80:
            return "매우 선호"
        if self.score >= 60:
            return "선호"
        if self.score >= 45:
            return "중립"
        return "관심 밖"


def preference_score(symbol: str, profile: UserProfile) -> PreferenceResult:
    """종목이 사용자 취향에 얼마나 맞는지 0~100 으로 산출한다.

    - 즐겨찾기: 강한 선호(85점 이상)
    - 선호 테마 소속: 테마 가중치에 비례(50~100)
    - 둘 다 아니면 중립(50)
    여러 근거 중 가장 강한 것을 점수로 삼는다(max).
    """
    score = 50.0  # 중립 기본
    reasons: list[str] = []

    if profile.is_favorite(symbol):
        score = max(score, 85.0)
        reasons.append("⭐ 즐겨찾기 종목")

    themes = symbol_themes(symbol)
    matched = [t for t in themes if t in profile.theme_weights]
    if matched:
        # 선호 테마 가중치(0~100) -> 50~100 으로 변환, 그중 최대 적용
        best_w = max(profile.theme_weights[t] for t in matched)
        themed_score = 50 + best_w / 2
        if themed_score > score:
            score = themed_score
        reasons.append(f"선호 테마 소속: {', '.join(matched)} (가중치 최대 {best_w})")
    elif themes:
        reasons.append(f"테마: {', '.join(themes)} (선호 목록엔 없음)")

    if not reasons:
        reasons.append("선호 테마/즐겨찾기에 해당 없음 (중립)")

    return PreferenceResult(
        score=round(float(score), 1),
        reasons=reasons,
        matched_themes=matched,
    )
