"""주식/ETF 분석 대시보드 (Streamlit) — 1~3단계.

1단계 시장 트렌드 · 2단계 뉴스 호재 · 3단계 사용자 선호 카테고리.
실행:  ./venv/bin/streamlit run app.py
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from trading.data import get_source
from trading.analysis import trend_score
from trading.news import get_news_source, news_score
from trading.storage import get_storage
from trading.profile import UserProfile, preference_score, all_theme_names, THEMES

st.set_page_config(page_title="AI 트레이딩 대시보드", layout="wide")
st.title("📈 AI 트레이딩 대시보드")
st.caption("1~3단계: 트렌드 + 뉴스 호재 + 내 취향 · 모의/백테스팅 기반 (실거래 아님)")

storage = get_storage("local")


@st.cache_data(ttl=600, show_spinner=False)
def fetch_news(query: str, market: str):
    """뉴스 수집 + 호재 점수. 10분 캐시로 중복 요청을 줄인다."""
    items = get_news_source("google").search(query, market=market, limit=30)
    return news_score(items)


# 프로필을 세션에 1회 로드 (이후 편집은 세션 상태에서)
if "profile" not in st.session_state:
    st.session_state.profile = UserProfile.from_dict(storage.load_profile())
profile: UserProfile = st.session_state.profile

# ── 사이드바: 종목 선택 + 내 투자 취향 ─────────────────────
with st.sidebar:
    st.header("종목 선택")
    symbol = st.text_input("종목코드 / 티커", value="005930",
                           help="한국: 6자리 숫자(예 005930) · 미국: 티커(예 AAPL)")
    symbol = symbol.strip()
    start = st.date_input("조회 시작일", value=None)

    st.divider()
    st.header("⚙️ 내 투자 취향")

    selected = st.multiselect("선호 테마", all_theme_names(),
                              default=list(profile.theme_weights.keys()),
                              format_func=lambda t: f"{THEMES[t]['emoji']} {t}")
    new_weights: dict[str, int] = {}
    for t in selected:
        new_weights[t] = st.slider(f"{THEMES[t]['emoji']} {t} 가중치", 0, 100,
                                   value=profile.theme_weights.get(t, 60), step=10)

    fav = st.checkbox(f"⭐ '{symbol}' 즐겨찾기", value=profile.is_favorite(symbol))

    if st.button("💾 취향 저장", use_container_width=True):
        profile.theme_weights = new_weights
        favs = set(profile.favorites)
        favs.add(symbol) if fav else favs.discard(symbol)
        profile.favorites = sorted(favs)
        storage.save_profile(profile.to_dict())
        st.success("저장했어요!")

    if profile.favorites:
        st.caption("⭐ 즐겨찾기: " + ", ".join(profile.favorites))

# ── 분석 ──────────────────────────────────────────────
if symbol:
    src = get_source("fdr")
    start_str = start.isoformat() if start else "2023-01-01"
    try:
        price = src.get_price(symbol, start=start_str)
    except Exception as e:  # noqa: BLE001
        st.error(f"데이터를 가져오지 못했습니다: {e}")
        st.stop()

    result = trend_score(price.df)
    ind = result.indicators
    news = fetch_news(price.name, price.market)
    pref = preference_score(symbol, profile)

    st.subheader(f"{price.name} ({price.symbol})")

    # 상단 요약: 시장/종가 + 3개 점수
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("시장", price.market)
    c2.metric("최근 종가", f"{price.last_close:,.2f}")
    c3.metric("📈 추세 점수", f"{result.score}", result.label)
    c4.metric("📰 뉴스 호재", f"{news.score}", news.label)
    c5.metric("⚙️ 내 선호도", f"{pref.score}", pref.label)

    # 가격 + 이동평균 차트
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=ind.index, open=ind["Open"], high=ind["High"],
        low=ind["Low"], close=ind["Close"], name="가격"))
    for ma, color in [("MA20", "orange"), ("MA60", "green"), ("MA120", "red")]:
        fig.add_trace(go.Scatter(x=ind.index, y=ind[ma], name=ma,
                                 line=dict(width=1, color=color)))
    fig.update_layout(height=460, xaxis_rangeslider_visible=False,
                      margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # 점수 근거 3단 (트렌드 / 뉴스 / 선호도)
    col_t, col_n, col_p = st.columns(3)
    with col_t:
        st.subheader("📈 추세 근거")
        for r in result.reasons:
            st.write(f"- {r}")
    with col_n:
        st.subheader(f"📰 뉴스 근거 (신뢰도 {news.confidence})")
        for r in news.reasons:
            st.write(f"- {r}")
    with col_p:
        st.subheader("⚙️ 선호도 근거")
        for r in pref.reasons:
            st.write(f"- {r}")

    # 최신 뉴스 목록
    if news.top_news:
        with st.expander(f"📰 최신 뉴스 {len(news.top_news)}건 보기"):
            for it in news.top_news:
                when = it.published.strftime("%m/%d") if it.published else ""
                st.markdown(f"- [{it.title}]({it.link})  ·  {it.source} {when}")

    st.info("다음 단계 예정: ④ 세 점수를 합친 종합 매수/매도 시그널")
