"""주식/ETF 분석 대시보드 (Streamlit).

종목 분석(트렌드·뉴스·취향 → 시그널 + 백테스트) + 모의투자 자동운용 현황.
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
from trading.paper import (
    PaperAccount, run_paper_trading, target_universe, record_snapshot, load_equity_history,
)
from trading.paper.trader import to_krw

st.set_page_config(page_title="AI 트레이딩 대시보드", layout="wide")
st.title("📈 AI 트레이딩 대시보드")
st.caption("트렌드+뉴스+취향 → 시그널 · 백테스트 · 모의투자 자동운용 (실거래 아님)")

storage = get_storage("local")
data_src = get_source("fdr")
news_src = get_news_source("google")
PAPER_KEY = "_paper"


@st.cache_data(ttl=600, show_spinner="분석 중…")
def run_analysis(symbol: str, start: str, weights: tuple, _profile: UserProfile):
    """종목 종합 분석. 10분 캐시. weights는 캐시키용 tuple."""
    w = {"trend": weights[0], "news": weights[1], "pref": weights[2]}
    return analyze_symbol(symbol, _profile, data_src, news_src, start=start, weights=w)


@st.cache_data(ttl=300, show_spinner=False)
def holding_prices(symbols: tuple) -> dict:
    """보유종목 현재가(원화환산). 5분 캐시."""
    out: dict[str, float] = {}
    for s in symbols:
        try:
            p = data_src.get_price(s, "2024-01-01")
            out[s] = to_krw(p.last_close, p.market)
        except Exception:  # noqa: BLE001
            pass
    return out


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
    st.caption("세 점수를 합칠 비율 (백테스팅에서 튜닝)")
    wt = st.slider("📈 추세", 0, 100, int(DEFAULT_WEIGHTS["trend"] * 100), 5)
    wn = st.slider("📰 뉴스", 0, 100, int(DEFAULT_WEIGHTS["news"] * 100), 5)
    wp = st.slider("⚙️ 선호", 0, 100, int(DEFAULT_WEIGHTS["pref"] * 100), 5)
    wsum = wt + wn + wp or 1
    weights = (wt / wsum, wn / wsum, wp / wsum)
    st.caption(f"정규화: 추세 {weights[0]:.0%} · 뉴스 {weights[1]:.0%} · 선호 {weights[2]:.0%}")

tab_analysis, tab_paper = st.tabs(["📊 종목 분석", "💼 모의투자"])

# ── 탭1: 종목 분석 ────────────────────────────────────
with tab_analysis:
    if not symbol:
        st.info("왼쪽에서 종목코드를 입력하세요.")
    else:
        start_str = start.isoformat() if start else "2023-01-01"
        try:
            a = run_analysis(symbol, start_str, weights, profile)
        except Exception as e:  # noqa: BLE001
            st.error(f"데이터를 가져오지 못했습니다: {e}")
            a = None
        if a is not None:
            sig = a.signal
            st.subheader(f"{a.price.name} ({a.price.symbol})")
            st.markdown(f"## {sig.emoji} 종합 시그널: **{sig.action}**  ·  {sig.total} / 100")
            (st.success if sig.action == "매수" else
             st.error if sig.action == "매도" else st.warning)(sig.reasons[0])
            st.caption("⚠️ 참고용 신호입니다. 투자 판단·책임은 본인에게 있습니다.")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("시장", a.price.market)
            c2.metric("최근 종가", f"{a.price.last_close:,.2f}")
            c3.metric("📈 추세 점수", f"{a.trend.score}", a.trend.label)
            c4.metric("📰 뉴스 호재", f"{a.news.score}", a.news.label)
            c5.metric("⚙️ 내 선호도", f"{a.pref.score}", a.pref.label)

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

            if a.news.top_news:
                with st.expander(f"📰 최신 뉴스 {len(a.news.top_news)}건 보기"):
                    for it in a.news.top_news:
                        when = it.published.strftime("%m/%d") if it.published else ""
                        st.markdown(f"- [{it.title}]({it.link})  ·  {it.source} {when}")

            # 백테스트 (트렌드 전략)
            st.divider()
            st.subheader("🧪 백테스트 — 추세 점수 전략")
            st.caption("추세 ≥ 매수선 보유, ≤ 매도선 현금. 트렌드만 검증. t일 신호→t+1 체결.")
            bc1, bc2, bc3 = st.columns(3)
            buy_th = bc1.slider("매수 임계값", 50, 90, 60, 5)
            sell_th = bc2.slider("매도 임계값", 10, 55, 45, 5)
            fee_pct = bc3.slider("거래비용 %", 0.0, 0.5, 0.15, 0.05)
            bt = run_backtest(ind, buy_th=buy_th, sell_th=sell_th, fee=fee_pct / 100)
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("전략 총수익", f"{bt.total_return*100:+.1f}%",
                      f"B&H 대비 {(bt.total_return-bt.bnh_return)*100:+.1f}%p")
            m2.metric("연복리(CAGR)", f"{bt.cagr*100:+.1f}%")
            m3.metric("최대낙폭(MDD)", f"{bt.mdd*100:.1f}%")
            m4.metric("샤프지수", f"{bt.sharpe:.2f}")
            m5.metric("승률", f"{bt.win_rate*100:.0f}%", f"{bt.n_trades}회")
            close = ind["Close"]
            bnh = close / close.iloc[0]
            eq_fig = go.Figure()
            eq_fig.add_trace(go.Scatter(x=bt.equity.index, y=bt.equity, name="전략",
                                        line=dict(color="#2E86DE", width=2)))
            eq_fig.add_trace(go.Scatter(x=bnh.index, y=bnh, name="Buy & Hold",
                                        line=dict(color="gray", width=1, dash="dash")))
            eq_fig.update_layout(height=300, margin=dict(t=10, b=10),
                                 yaxis_title="누적자산(시작=1.0)")
            st.plotly_chart(eq_fig, use_container_width=True)
            st.caption(f"⚠️ 단순 추세추종 과거 시뮬레이션. 미래 보장 안 됨. ({bt.summary()})")

# ── 탭2: 모의투자 ────────────────────────────────────
with tab_paper:
    st.subheader("💼 모의투자 자동운용")
    st.caption("가상 1천만원으로 시그널 따라 자동매매 · 실거래 아님 · 매매는 watch.py 또는 아래 버튼")
    account = PaperAccount.from_dict(storage.load_profile(PAPER_KEY))
    prices = holding_prices(tuple(account.holdings))

    total = account.total_value(prices)
    ret = account.total_return(prices)
    c1, c2, c3 = st.columns(3)
    c1.metric("총자산", f"{total:,.0f}원", f"{ret*100:+.2f}%")
    c2.metric("현금", f"{account.cash:,.0f}원")
    c3.metric("보유", f"{len(account.holdings)}종목")

    b1, b2 = st.columns(2)
    if b1.button("🔄 지금 자동운용 1회", use_container_width=True):
        uni = target_universe(profile)
        if not uni:
            st.warning("운용 대상이 없어요. 사이드바에서 선호 테마나 즐겨찾기를 등록하세요.")
        else:
            with st.spinner(f"{len(uni)}종목 분석·매매 중…"):
                trades, px = run_paper_trading(account, profile, data_src, news_src, uni)
                storage.save_profile(account.to_dict(), PAPER_KEY)
                record_snapshot(storage, account, px)  # 자산 시계열 누적
            st.success(f"체결 {len(trades)}건 완료!")
            st.cache_data.clear()
            st.rerun()
    if b2.button("♻️ 계좌 초기화 (가상자본 리셋)", use_container_width=True):
        storage.save_profile(PaperAccount().to_dict(), PAPER_KEY)
        st.rerun()

    # 자산곡선 (저널 시계열 — 며칠 굴릴수록 풍부해짐)
    eq_hist = load_equity_history(storage)
    if len(eq_hist) >= 2:
        st.markdown("**자산 추이**")
        dates = [h["date"] for h in eq_hist]
        totals = [h["total"] for h in eq_hist]
        jf = go.Figure()
        jf.add_trace(go.Scatter(x=dates, y=totals, name="총자산", fill="tozeroy",
                                line=dict(color="#2E86DE", width=2)))
        jf.add_hline(y=account.initial_capital, line=dict(color="gray", dash="dash"),
                     annotation_text="초기자본")
        jf.update_layout(height=260, margin=dict(t=10, b=10), yaxis_title="총자산(원)")
        st.plotly_chart(jf, use_container_width=True)
    elif eq_hist:
        st.caption(f"📈 자산 추이 그래프는 데이터가 2일 이상 쌓이면 표시돼요 (현재 {len(eq_hist)}개 기록).")

    if account.holdings:
        st.markdown("**보유 종목**")
        rows = []
        for s, h in account.holdings.items():
            px = prices.get(s, h.avg_price)
            pnl, pct = account.position_pnl(s, px)
            name = next((r["name"] for r in reversed(account.history)
                         if r["symbol"] == s and r.get("name")), s)
            rows.append({"종목": f"{name}({s})", "수량": h.shares,
                         "평단": f"{h.avg_price:,.0f}", "현재가": f"{px:,.0f}",
                         "손익": f"{pnl:,.0f}", "수익률": f"{pct*100:+.1f}%"})
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("보유 종목이 없어요. '지금 자동운용 1회'를 누르거나 watch.py를 돌려보세요.")

    if account.history:
        with st.expander(f"📒 거래 내역 {len(account.history)}건"):
            hist = [{"일시": r["date"][5:16], "종목": r.get("name") or r["symbol"],
                     "구분": r["action"], "수량": r["shares"],
                     "체결가": f"{r['price']:,.0f}", "금액": f"{r['amount']:,.0f}",
                     "손익": f"{r.get('pnl', ''):,}" if r.get("pnl") else ""}
                    for r in reversed(account.history)]
            st.dataframe(hist, use_container_width=True, hide_index=True)
