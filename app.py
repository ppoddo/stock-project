"""주식/ETF 분석 대시보드 (Streamlit) — 1~5.5단계.

트렌드·뉴스·취향 → 종합 시그널 + 트렌드 전략 백테스팅.
실행:  ./venv/bin/streamlit run app.py
"""
from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from trading.data import get_source
from trading.news import get_news_source
from trading.storage import get_storage
from trading.profile import UserProfile, all_theme_names, THEMES
from trading.signal import analyze_symbol, DEFAULT_WEIGHTS
from trading.backtest import run_backtest

st.set_page_config(page_title="AI 트레이딩 대시보드", layout="wide")
st.title("📈 AI 트레이딩 대시보드")
st.caption("트렌드+뉴스+취향 → 종합 시그널 · 트렌드 전략 백테스팅 · 모의 기반 (실거래 아님)")

storage = get_storage("local")
data_src = get_source("fdr")
news_src = get_news_source("google")


@st.cache_data(ttl=600, show_spinner="분석 중…")
def run_analysis(symbol: str, start: str, weights: tuple, _profile: UserProfile):
    """종목 종합 분석. 10분 캐시. weights는 캐시키용 tuple."""
    w = {"trend": weights[0], "news": weights[1], "pref": weights[2]}
    return analyze_symbol(symbol, _profile, data_src, news_src, start=start, weights=w)


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

    st.divider()
    st.header("🎚️ 시그널 가중치")
    st.caption("세 점수를 합칠 비율 (5단계 백테스팅에서 튜닝 예정)")
    wt = st.slider("📈 추세", 0, 100, int(DEFAULT_WEIGHTS["trend"] * 100), 5)
    wn = st.slider("📰 뉴스", 0, 100, int(DEFAULT_WEIGHTS["news"] * 100), 5)
    wp = st.slider("⚙️ 선호", 0, 100, int(DEFAULT_WEIGHTS["pref"] * 100), 5)
    wsum = wt + wn + wp or 1
    weights = (wt / wsum, wn / wsum, wp / wsum)  # 합 1.0 정규화
    st.caption(f"정규화: 추세 {weights[0]:.0%} · 뉴스 {weights[1]:.0%} · 선호 {weights[2]:.0%}")

# ── 분석 ──────────────────────────────────────────────
if symbol:
    start_str = start.isoformat() if start else "2023-01-01"
    try:
        a = run_analysis(symbol, start_str, weights, profile)
    except Exception as e:  # noqa: BLE001
        st.error(f"데이터를 가져오지 못했습니다: {e}")
        st.stop()

    sig = a.signal
    st.subheader(f"{a.price.name} ({a.price.symbol})")

    # 종합 시그널 배너
    st.markdown(f"## {sig.emoji} 종합 시그널: **{sig.action}**  ·  {sig.total} / 100")
    if sig.action == "매수":
        st.success(sig.reasons[0])
    elif sig.action == "매도":
        st.error(sig.reasons[0])
    else:
        st.warning(sig.reasons[0])
    st.caption("⚠️ 참고용 신호입니다. 투자 판단·책임은 본인에게 있습니다.")

    # 상단 요약: 시장/종가 + 3개 점수
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("시장", a.price.market)
    c2.metric("최근 종가", f"{a.price.last_close:,.2f}")
    c3.metric("📈 추세 점수", f"{a.trend.score}", a.trend.label)
    c4.metric("📰 뉴스 호재", f"{a.news.score}", a.news.label)
    c5.metric("⚙️ 내 선호도", f"{a.pref.score}", a.pref.label)

    # 가격 + 이동평균 차트
    ind = a.trend.indicators
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
        for r in a.trend.reasons:
            st.write(f"- {r}")
    with col_n:
        st.subheader(f"📰 뉴스 근거 (신뢰도 {a.news.confidence})")
        for r in a.news.reasons:
            st.write(f"- {r}")
    with col_p:
        st.subheader("⚙️ 선호도 근거")
        for r in a.pref.reasons:
            st.write(f"- {r}")

    # 최신 뉴스 목록
    if a.news.top_news:
        with st.expander(f"📰 최신 뉴스 {len(a.news.top_news)}건 보기"):
            for it in a.news.top_news:
                when = it.published.strftime("%m/%d") if it.published else ""
                st.markdown(f"- [{it.title}]({it.link})  ·  {it.source} {when}")

    # ── 백테스트 (트렌드 전략) ─────────────────────────────
    st.divider()
    st.subheader("🧪 백테스트 — 추세 점수 전략")
    st.caption("추세 점수 ≥ 매수선이면 보유, ≤ 매도선이면 현금. "
               "과거 데이터로 검증(뉴스·선호 제외, 트렌드만). t일 신호→t+1 체결.")
    bc1, bc2, bc3 = st.columns(3)
    buy_th = bc1.slider("매수 임계값", 50, 90, 60, 5)
    sell_th = bc2.slider("매도 임계값", 10, 55, 45, 5)
    fee_pct = bc3.slider("거래비용 %", 0.0, 0.5, 0.15, 0.05)

    bt = run_backtest(a.trend.indicators, buy_th=buy_th, sell_th=sell_th, fee=fee_pct / 100)
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("전략 총수익", f"{bt.total_return*100:+.1f}%",
              f"B&H 대비 {(bt.total_return-bt.bnh_return)*100:+.1f}%p")
    m2.metric("연복리(CAGR)", f"{bt.cagr*100:+.1f}%")
    m3.metric("최대낙폭(MDD)", f"{bt.mdd*100:.1f}%")
    m4.metric("샤프지수", f"{bt.sharpe:.2f}")
    m5.metric("승률", f"{bt.win_rate*100:.0f}%", f"{bt.n_trades}회 거래")

    # 자산곡선 vs Buy & Hold
    close = a.trend.indicators["Close"]
    bnh = close / close.iloc[0]
    eq_fig = go.Figure()
    eq_fig.add_trace(go.Scatter(x=bt.equity.index, y=bt.equity, name="전략",
                                line=dict(color="#2E86DE", width=2)))
    eq_fig.add_trace(go.Scatter(x=bnh.index, y=bnh, name="Buy & Hold",
                                line=dict(color="gray", width=1, dash="dash")))
    eq_fig.update_layout(height=300, margin=dict(t=10, b=10),
                         yaxis_title="누적자산(시작=1.0)")
    st.plotly_chart(eq_fig, use_container_width=True)
    st.caption(f"⚠️ 단순 추세추종 전략의 과거 시뮬레이션입니다. 미래 수익을 보장하지 않으며, "
               f"투자 판단·책임은 본인에게 있습니다. ({bt.summary()})")
