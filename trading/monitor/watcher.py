"""감시 워커 (5단계).

관심종목(즐겨찾기)을 순회하며 analyze_symbol 로 시그널을 계산하고,
알림 대상 행동(기본: 매수/매도)이 '직전과 달라졌을 때만' 알림을 보낸다.
→ 같은 신호를 주기마다 반복 발송하는 스팸을 막는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..data.base import DataSource
from ..news.base import NewsSource
from ..notify.base import Notifier
from ..storage.base import Storage
from ..profile import UserProfile
from ..signal import analyze_symbol, Analysis

# 감시 상태(직전 행동)는 이 키로 저장소에 저장한다.
_STATE_KEY = "_watch_state"


def build_message(a: Analysis) -> str:
    """알림 메시지(텔레그램 HTML)를 만든다."""
    s = a.signal
    return (
        f"{s.emoji} <b>{a.price.name}</b> ({a.price.symbol}) — <b>{s.action}</b>\n"
        f"종합 {s.total}/100  ·  최근가 {a.price.last_close:,.2f}\n"
        f"📈추세 {s.trend} · 📰뉴스 {s.news} · ⚙️선호 {s.pref}\n"
        f"<i>⚠️ 참고용 신호 · 투자 판단은 본인 책임</i>"
    )


@dataclass
class WatchReport:
    """한 번 순회한 결과 요약."""

    checked: list[str]          # 점검한 종목
    alerted: list[str]          # 알림 보낸 종목
    errors: dict[str, str]      # 종목별 오류


def run_watch(symbols: list[str], profile: UserProfile,
              data_source: DataSource, news_source: NewsSource,
              notifier: Notifier, storage: Storage,
              weights: dict[str, float] | None = None,
              alert_actions: tuple[str, ...] = ("매수", "매도")) -> WatchReport:
    """관심종목을 한 번 순회하며 조건 충족 종목만 알림한다."""
    state = storage.load_profile(_STATE_KEY)  # {symbol: last_action}
    checked, alerted, errors = [], [], {}

    for sym in symbols:
        try:
            a = analyze_symbol(sym, profile, data_source, news_source, weights=weights)
            checked.append(sym)
            action = a.signal.action
            # 알림 대상 행동이고, 직전과 달라졌을 때만 발송
            if action in alert_actions and state.get(sym) != action:
                if notifier.send(build_message(a)):
                    alerted.append(sym)
            state[sym] = action  # 행동 갱신(관망 전환도 기록해 다음 변화 감지)
        except Exception as e:  # noqa: BLE001 - 한 종목 실패가 전체를 막지 않게
            errors[sym] = str(e)

    storage.save_profile(state, _STATE_KEY)
    return WatchReport(checked=checked, alerted=alerted, errors=errors)
