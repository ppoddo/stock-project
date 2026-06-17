"""주식/ETF 분석 대시보드 (Streamlit) — 1단계: 시장 트렌드 분석.

실행:  ./venv/bin/streamlit run app.py
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from trading.data import get_source
from trading.analysis import trend_score
from trading.news import get_news_source, news_score

st.set_page_config(page_title="AI 트레이딩 대시보드", layout="wide")
st.title("📈 AI 트레이딩 대시보드")
st.caption("1~2단계: 시장 트렌드 + 뉴스 호재 분석 · 모의/백테스팅 기반 (실거래 아님)")


@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(query: str, market: str):
    """뉴스 수집 + 호재 점수. 10분 캐시로 중복 요청을 줄인다."""
    items = get_news_source("google").search(query, market=market, limit=30)
    return news_score(items)

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

    # 뉴스 호재 분석 (종목명으로 검색)
    news = fetch_news(price.name, price.market)

    st.subheader(f"{price.name} ({price.symbol})")

    # 상단 요약
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("시장", price.market)
    c2.metric("최근 종가", f"{price.last_close:,.2f}")
    c3.metric("추세 점수", f"{result.score} / 100", result.label)
    c4.metric("뉴스 호재 점수", f"{news.score} / 100", news.label)

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

    # 점수 근거 (트렌드 / 뉴스 나란히)
    col_t, col_n = st.columns(2)
    with col_t:
        st.subheader("📈 추세 점수 근거")
        for r in result.reasons:
            st.write(f"- {r}")
    with col_n:
        st.subheader(f"📰 뉴스 호재 근거 (신뢰도 {news.confidence})")
        for r in news.reasons:
            st.write(f"- {r}")

    # 최신 뉴스 목록
    if news.top_news:
        with st.expander(f"📰 최신 뉴스 {len(news.top_news)}건 보기"):
            for it in news.top_news:
                when = it.published.strftime("%m/%d") if it.published else ""
                st.markdown(f"- [{it.title}]({it.link})  ·  {it.source} {when}")

    st.info("다음 단계 예정: ③ 선호 카테고리 가중치 · ④ 종합 매수/매도 시그널")
