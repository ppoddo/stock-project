"""시장 트렌드 분석 (요구사항 ①).

가격 시계열에 기술적 지표를 붙이고, 0~100 의 '추세 점수'를 매긴다.
점수가 높을수록 상승 추세 / 매수 우호적이라는 뜻이다.

이 점수는 4단계 시그널 엔진에서 뉴스 점수·선호도와 합쳐진다.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """이동평균(20/60/120), RSI(14), MACD 를 계산해 컬럼으로 붙인다."""
    out = df.copy()
    close = out["Close"]

    # 이동평균선
    out["MA20"] = close.rolling(20).mean()
    out["MA60"] = close.rolling(60).mean()
    out["MA120"] = close.rolling(120).mean()

    # RSI(14): 상대강도지수
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))

    # MACD: 12일 EMA - 26일 EMA, 시그널은 9일 EMA
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_signal"] = out["MACD"].ewm(span=9, adjust=False).mean()

    return out


@dataclass
class TrendResult:
    """추세 분석 결과 요약."""

    score: float                 # 0~100 추세 점수
    reasons: list[str]           # 점수 근거 (사람이 읽는 설명)
    indicators: pd.DataFrame     # 지표가 붙은 전체 데이터프레임

    @property
    def label(self) -> str:
        if self.score >= 70:
            return "강한 상승 추세"
        if self.score >= 55:
            return "약한 상승 추세"
        if self.score >= 45:
            return "중립"
        if self.score >= 30:
            return "약한 하락 추세"
        return "강한 하락 추세"


def trend_score(df: pd.DataFrame) -> TrendResult:
    """여러 지표를 종합해 0~100 추세 점수를 산출한다.

    각 신호를 동일 가중으로 더한 뒤 0~100 으로 정규화한다.
    (가중치는 4단계에서 백테스팅으로 튜닝할 예정 — 지금은 단순/투명하게)
    """
    ind = add_indicators(df)
    last = ind.iloc[-1]
    reasons: list[str] = []
    signals: list[float] = []  # 각 항목 -1(약세) ~ +1(강세)

    # 1) 종가 > 20일선 : 단기 상승
    if not np.isnan(last["MA20"]):
        up = last["Close"] > last["MA20"]
        signals.append(1.0 if up else -1.0)
        reasons.append(f"종가가 20일선 {'위' if up else '아래'}")

    # 2) 20일선 > 60일선 : 정배열(중기 상승)
    if not np.isnan(last["MA60"]):
        up = last["MA20"] > last["MA60"]
        signals.append(1.0 if up else -1.0)
        reasons.append(f"20일선이 60일선 {'위(정배열)' if up else '아래(역배열)'}")

    # 3) RSI : 50 기준 강세/약세, 단 과열(>70)/침체(<30)는 약하게 반영
    if not np.isnan(last["RSI"]):
        rsi = last["RSI"]
        if rsi >= 70:
            signals.append(0.2)
            reasons.append(f"RSI {rsi:.0f} (과열 — 조정 주의)")
        elif rsi <= 30:
            signals.append(-0.2)
            reasons.append(f"RSI {rsi:.0f} (과매도 — 반등 가능)")
        else:
            s = (rsi - 50) / 20  # -1~+1 근처
            signals.append(float(np.clip(s, -1, 1)))
            reasons.append(f"RSI {rsi:.0f}")

    # 4) MACD > 시그널 : 모멘텀 상승
    if not np.isnan(last["MACD"]):
        up = last["MACD"] > last["MACD_signal"]
        signals.append(1.0 if up else -1.0)
        reasons.append(f"MACD가 시그널선 {'위' if up else '아래'}")

    # 5) 최근 20일 수익률 추세
    if len(ind) >= 21:
        ret20 = ind["Close"].iloc[-1] / ind["Close"].iloc[-21] - 1
        signals.append(float(np.clip(ret20 * 5, -1, 1)))
        reasons.append(f"최근 20일 수익률 {ret20*100:+.1f}%")

    avg = np.mean(signals) if signals else 0.0
    score = (avg + 1) / 2 * 100  # -1~+1 -> 0~100
    return TrendResult(score=round(float(score), 1), reasons=reasons, indicators=ind)
