"""뉴스 호재 점수 (요구사항 ②).

기사 제목·요약에서 호재/악재 키워드를 세어 0~100 점수를 매긴다.
- 50점 = 중립, 높을수록 호재 우세
- 룰(키워드) 기반이라 빠르고 투명하다. 비용/키 불필요.
- 추후 Claude API 기반 감성 분석으로 업그레이드 가능 (CLAUDE.md 확장 포인트).

가중치·키워드 사전은 백테스팅으로 보강 예정 — 지금은 단순/투명하게.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .base import NewsItem

# 호재(긍정) 키워드 — 한국어 + 영어
POSITIVE = [
    # 한국어
    "급등", "상승", "신고가", "최고가", "사상최대", "역대최대", "호실적", "흑자", "흑자전환",
    "수주", "대규모 계약", "계약", "돌파", "강세", "매수", "목표가 상향", "상향", "수혜",
    "성장", "확대", "신제품", "출시", "기대", "회복", "반등", "선방", "어닝서프라이즈", "배당",
    # 영어
    "surge", "soar", "jump", "rally", "record high", "beat", "upgrade", "bullish",
    "profit", "growth", "outperform", "buy rating", "all-time high", "rebound", "boost",
]

# 악재(부정) 키워드 — 한국어 + 영어
NEGATIVE = [
    # 한국어
    "급락", "하락", "신저가", "최저가", "적자", "적자전환", "손실", "부진", "리콜", "소송",
    "목표가 하향", "하향", "약세", "매도", "우려", "위기", "감산", "감원", "구조조정",
    "악재", "충격", "쇼크", "경고", "리스크", "제재", "벌금", "횡령", "분식", "디폴트",
    # 영어
    "plunge", "plummet", "drop", "tumble", "miss", "downgrade", "bearish", "loss",
    "lawsuit", "decline", "sell rating", "warning", "cut", "slump", "crash", "recall",
]


def _count_hits(text: str, keywords: list[str]) -> list[str]:
    """텍스트에서 매칭된 키워드 목록을 반환한다."""
    low = text.lower()
    hits = []
    for kw in keywords:
        # 영어는 단어 경계, 한국어는 부분 매칭
        if re.search(r"[a-zA-Z]", kw):
            if re.search(rf"\b{re.escape(kw.lower())}\b", low):
                hits.append(kw)
        elif kw in text:
            hits.append(kw)
    return hits


@dataclass
class NewsResult:
    """뉴스 호재 분석 결과."""

    score: float              # 0~100 호재 점수 (50=중립)
    n_articles: int           # 분석한 기사 수
    n_positive: int           # 호재 기사 수
    n_negative: int           # 악재 기사 수
    reasons: list[str]        # 근거 (대표 호재/악재 키워드 등)
    top_news: list[NewsItem]  # 대표 기사 (최신순 일부)

    @property
    def label(self) -> str:
        if self.n_articles == 0:
            return "뉴스 없음"
        if self.score >= 65:
            return "호재 우세"
        if self.score >= 55:
            return "약한 호재"
        if self.score >= 45:
            return "중립"
        if self.score >= 35:
            return "약한 악재"
        return "악재 우세"

    @property
    def confidence(self) -> str:
        """기사 수 기반 신뢰도 — 적으면 점수를 덜 믿어야 한다."""
        if self.n_articles >= 15:
            return "높음"
        if self.n_articles >= 5:
            return "보통"
        return "낮음"


def news_score(items: list[NewsItem]) -> NewsResult:
    """뉴스 목록을 받아 호재 점수를 산출한다."""
    if not items:
        return NewsResult(50.0, 0, 0, 0, ["수집된 뉴스가 없습니다"], [])

    article_scores: list[float] = []
    pos_count = neg_count = 0
    pos_hits: dict[str, int] = {}
    neg_hits: dict[str, int] = {}

    for it in items:
        p = _count_hits(it.text, POSITIVE)
        n = _count_hits(it.text, NEGATIVE)
        for kw in p:
            pos_hits[kw] = pos_hits.get(kw, 0) + 1
        for kw in n:
            neg_hits[kw] = neg_hits.get(kw, 0) + 1
        net = len(p) - len(n)
        if net > 0:
            pos_count += 1
        elif net < 0:
            neg_count += 1
        # 기사별 점수: -1~+1 로 클립 (한 기사가 과도하게 좌우하지 않도록)
        article_scores.append(max(-1.0, min(1.0, net)))

    avg = sum(article_scores) / len(article_scores)
    score = round((avg + 1) / 2 * 100, 1)  # -1~1 -> 0~100

    reasons: list[str] = [
        f"호재 기사 {pos_count}건 · 악재 기사 {neg_count}건 (총 {len(items)}건)"
    ]
    if pos_hits:
        top_pos = sorted(pos_hits.items(), key=lambda x: -x[1])[:3]
        reasons.append("주요 호재어: " + ", ".join(f"{k}({v})" for k, v in top_pos))
    if neg_hits:
        top_neg = sorted(neg_hits.items(), key=lambda x: -x[1])[:3]
        reasons.append("주요 악재어: " + ", ".join(f"{k}({v})" for k, v in top_neg))

    return NewsResult(
        score=score,
        n_articles=len(items),
        n_positive=pos_count,
        n_negative=neg_count,
        reasons=reasons,
        top_news=items[:8],
    )
