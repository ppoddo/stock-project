"""투자 테마 정의 + 대표 종목 매핑 (요구사항 ③).

각 테마에 대표 종목을 매핑해 둔다. 한 종목이 여러 테마에 속할 수 있다(예: 삼성전자=반도체).
※ 대표 종목은 예시이며 완전하지 않다. 사용자가 즐겨찾기로 보완하고,
   이 사전은 자유롭게 추가/수정하면 된다. (장기적으로 자동 분류로 확장 가능)
"""
from __future__ import annotations

# 테마 -> {이모지, 한/미 대표 종목코드 집합}
THEMES: dict[str, dict] = {
    "반도체": {
        "emoji": "💾",
        "symbols": {"005930", "000660", "000990", "042700",  # 삼성전자, SK하이닉스, DB하이텍, 한미반도체
                    "NVDA", "AMD", "TSM", "AVGO", "INTC", "MU"},
    },
    "2차전지": {
        "emoji": "🔋",
        "symbols": {"373220", "006400", "247540", "086520", "003670",  # LG엔솔, 삼성SDI, 에코프로비엠, 에코프로, 포스코퓨처엠
                    "TSLA", "ALB"},
    },
    "AI/소프트웨어": {
        "emoji": "🤖",
        "symbols": {"035420", "035720",  # 네이버, 카카오
                    "MSFT", "GOOGL", "META", "NVDA", "PLTR"},
    },
    "바이오/제약": {
        "emoji": "🧬",
        "symbols": {"207940", "068270", "326030",  # 삼성바이오로직스, 셀트리온, SK바이오팜
                    "LLY", "JNJ", "PFE"},
    },
    "자동차": {
        "emoji": "🚗",
        "symbols": {"005380", "000270", "012330",  # 현대차, 기아, 현대모비스
                    "TSLA", "F", "GM"},
    },
    "방산": {
        "emoji": "🛡️",
        "symbols": {"012450", "079550", "047810",  # 한화에어로스페이스, LIG넥스원, 한국항공우주
                    "LMT", "RTX"},
    },
    "배당/안정": {
        "emoji": "💰",
        "symbols": {"030200", "033780", "017670",  # KT, KT&G, SK텔레콤
                    "KO", "JNJ", "PG", "VZ", "SCHD"},
    },
    "빅테크": {
        "emoji": "🏢",
        "symbols": {"AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA"},
    },
}


def symbol_themes(symbol: str) -> list[str]:
    """종목이 속한 테마 목록을 반환한다."""
    return [name for name, t in THEMES.items() if symbol in t["symbols"]]


def all_theme_names() -> list[str]:
    return list(THEMES.keys())
