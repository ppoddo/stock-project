"""주식/ETF 분석 대시보드 (Streamlit) — 1단계: 시장 트렌드 분석.

실행:  ./venv/bin/streamlit run app.py
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from trading.data import get_source
from trading.analysis import trend_score

st.set_page_config(page_title="AI 트레이딩 대시보드", layout="wide")
st.title("📈 AI 트레이딩 대시보드")
st.caption("1단계: 시장 트렌드 분석 · 모의/백테스팅 기반 (실거래 아님)")

# ── 입력 ──────────────────────────────────────────────
with st.sidebar:
    st.header("종목 선택")
    symbol = st.text_input("종목코드 / 티커", value="005930",
                           help="한국: 6자리 숫자(예 005930) · 미국: 티커(예 AAPL)")
    start = st.date_input("조회 시작일", value=None)
    run = st.button("분석하기", type="primary", use_container_width=True)

# ── 분석 ──────────────────────────────────────────────
if run or symbol:
    src = get_source("fdr")
    start_str = start.isoformat() if start else "2023-01-01"
    try:
        price = src.get_price(symbol.strip(), start=start_str)
    except Exception as e:  # noqa: BLE001
        st.error(f"데이터를 가져오지 못했습니다: {e}")
        st.stop()

    result = trend_score(price.df)
    ind = result.indicators

    # 상단 요약
    c1, c2, c3 = st.columns(3)
    c1.metric("시장", price.market)
    c2.metric("최근 종가", f"{price.last_close:,.2f}")
    c3.metric("추세 점수", f"{result.score} / 100", result.label)

    # 가격 + 이동평균 차트
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=ind.index, open=ind["Open"], high=ind["High"],
        low=ind["Low"], close=ind["Close"], name="가격"))
    for ma, color in [("MA20", "orange"), ("MA60", "green"), ("MA120", "red")]:
        fig.add_trace(go.Scatter(x=ind.index, y=ind[ma], name=ma,
                                 line=dict(width=1, color=color)))
    fig.update_layout(height=480, xaxis_rangeslider_visible=False,
                      margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # 점수 근거
    st.subheader("📌 추세 점수 근거")
    for r in result.reasons:
        st.write(f"- {r}")

    st.info("다음 단계 예정: ② 뉴스 호재 분석 · ③ 선호 카테고리 · ④ 종합 시그널")
