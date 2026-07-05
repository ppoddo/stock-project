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
    "클라우드/SaaS": {
        "emoji": "☁️",
        "symbols": {"018260", "012510", "030520",  # 삼성에스디에스, 더존비즈온, 한글과컴퓨터
                    "ORCL", "CRM", "NOW", "ADBE", "SNOW"},
    },
    "게임/콘텐츠": {
        "emoji": "🎮",
        "symbols": {"259960", "036570", "251270", "352820",  # 크래프톤, 엔씨소프트, 넷마블, 하이브
                    "RBLX", "EA", "NFLX"},
    },
    "ETF/지수": {
        "emoji": "📦",
        # 소액으로도 살 수 있는 분산 수단 (개별주 1주가 배분액을 넘는 경우 대비)
        "symbols": {"069500", "360750", "133690",  # KODEX 200, TIGER 미국S&P500, TIGER 미국나스닥100
                    "SPY", "QQQ", "SCHD"},
    },
}


def symbol_themes(symbol: str) -> list[str]:
    """종목이 속한 테마 목록을 반환한다."""
    return [name for name, t in THEMES.items() if symbol in t["symbols"]]


def all_theme_names() -> list[str]:
    return list(THEMES.keys())
