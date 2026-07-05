# 상세 구현 플랜 — 모의투자 손실 진단 & 전략 수식 고도화 (WP1~WP4)

> 작성: Opus 플래너. 원본 마스터 플랜(Fable)을 현재 저장소 코드에 정확히 맞춰 구체화한 것.
> 워커는 이 문서를 그대로 따라 구현한다. **WP1→WP2→WP3→WP4 순서 고정**(같은 파일 충돌 방지).
> git commit 금지 — 작업트리에만 변경. 실거래 코드 금지. 분석/전략에서 FinanceDataReader 직접 import 금지(DataSource 경유). 점수/판단 함수는 reasons 동반. 주석·UI 한국어, 식별자 영어.

---

## WP0 (선행): 공용 설정 파일 신설 — `trading/config.py`

**목적**: 임계값·손절률·환율·쿨다운 등 WP2·WP3가 공유하는 파라미터를 한 곳에 모은다. 지금은 엔진 70/40 · 백테스트 60/45 가 불일치(마스터 플랜 손실원인 3). 이 파일이 단일 출처(single source of truth)가 된다.

**신설**: `trading/config.py`
```python
"""전략 공용 파라미터 (단일 출처).

시그널 임계값·손절·환율·쿨다운을 여기 모아 엔진/백테스트/모의투자가 공유한다.
WP3 그리드서치가 최적값을 찾으면 이 파일의 상수만 갱신하면 전 계층에 반영된다.
"""
from __future__ import annotations

# ── 시그널 임계값 (종합점수 0~100 기준) ──
# ※ WP3 튜닝 전 잠정값. 엔진과 백테스트가 동일 값을 쓰도록 통일.
BUY_THRESHOLD: float = 65.0
SELL_THRESHOLD: float = 45.0

# ── 백테스트용 추세 임계값 (트렌드 점수 0~100 기준) ──
BT_BUY_TH: float = 60.0
BT_SELL_TH: float = 45.0

# ── 손절 / 트레일링 스탑 (WP2) ──
STOP_LOSS_PCT: float = 0.08          # 평단 대비 -8% 이탈 시 손절
TRAILING_STOP_PCT: float = 0.10      # 보유 중 고점 대비 -10% 하락 시 청산
REENTRY_COOLDOWN_DAYS: int = 3       # 손절 후 재매수 금지 영업일

# ── 포지션 사이징 ──
POSITION_PCT: float = 0.20           # 종목당 초기자본 배분 비율

# ── 거래비용 ──
FEE: float = 0.0015                  # 왕복 근사

# ── 환율 폴백 (WP2에서 실시간 조회 실패 시) ──
FX_USD_KRW_FALLBACK: float = 1350.0
```

**하위호환**: 기존 모듈의 리터럴을 이 상수 재-export로 바꾼다(값·이름 유지, 출처만 통일).
- `trading/signal/engine.py`: `BUY_THRESHOLD`/`SELL_THRESHOLD` 를 `from ..config import BUY_THRESHOLD, SELL_THRESHOLD` 로 교체. `DEFAULT_WEIGHTS` 는 그대로 둔다(WP3에서 다룸). `combine_scores`/`decide_action` 시그니처 불변.
- `trading/backtest/engine.py`: `run_backtest` 기본값 `buy_th=60.0, sell_th=45.0` 를 `buy_th: float | None = None` 로 바꾸고 함수 안에서 `buy_th = BT_BUY_TH if buy_th is None else buy_th` (sell_th 동일). **호출부(app.py 슬라이더)는 명시값을 넘기므로 영향 없음.** `fee` 기본값도 `FEE` 참조.
- `trading/paper/account.py`: `FEE = 0.0015` → `from ..config import FEE`. `DEFAULT_CAPITAL` 는 그대로.
- `trading/paper/trader.py`: `FX_USD_KRW = 1350.0` 는 WP2에서 실시간 환율로 대체(아래).

**완료 기준**:
```bash
./venv/bin/python -c "from trading.config import BUY_THRESHOLD, STOP_LOSS_PCT, FEE; print(BUY_THRESHOLD, STOP_LOSS_PCT, FEE)"
./venv/bin/python -c "from trading.signal import BUY_THRESHOLD; from trading.backtest import run_backtest; print('ok', BUY_THRESHOLD)"
```

---

## WP1: 성과 분석 리포트 📊

**목표**: "왜 잃고 있나"를 계좌 mark-to-market + journal 시계열로 진단. journal 1행만 있어도 무에러 동작.

### 신설: `trading/paper/analytics.py`

```python
"""모의투자 성과 분석 (진단 리포트).

계좌를 현재가로 재평가(mark-to-market)하고 종목별 손익·기여도,
journal 시계열 기반 총수익률·MDD·일별 변동을 계산해 "왜 이 성과인지" reasons 로 설명한다.
데이터가 1행뿐이어도(운용 초기) 에러 없이 부분 결과 + "데이터 축적 중" 안내를 낸다.
⚠️ 가상계좌 분석 전용.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .account import PaperAccount


@dataclass
class PositionPnL:
    """종목별 손익 + 전체 손익 기여도."""
    symbol: str
    name: str
    shares: int
    avg_price: float
    cur_price: float
    pnl: float                 # 평가손익(원)
    pnl_pct: float             # 수익률
    contribution: float        # 전체 손익 대비 이 종목의 기여(원, 부호 유지)


@dataclass
class PerformanceReport:
    """계좌 성과 분석 결과."""
    total_value: float
    total_return: float        # 초기자본 대비
    cash: float
    positions: list[PositionPnL]
    mdd: float                 # journal 시계열 기반 최대낙폭(음수), 데이터 부족 시 0.0
    days_tracked: int          # journal 레코드 수
    best: PositionPnL | None
    worst: PositionPnL | None
    reasons: list[str] = field(default_factory=list)
    data_sufficient: bool = True   # journal >= 2 여야 시계열 지표 신뢰
```

**핵심 함수**:
```python
def analyze_performance(account: PaperAccount, prices: dict[str, float],
                        equity_history: list[dict] | None = None) -> PerformanceReport:
    """계좌를 현재가로 평가하고 종목별 손익·기여도·MDD·근거를 산출한다.

    prices: symbol -> 원화환산 현재가 (없는 종목은 avg_price 로 폴백; account.position_pnl 규약과 동일)
    equity_history: journal.load_equity_history() 결과. None/1행이면 시계열 지표는 0, data_sufficient=False.
    """
```

**로직 정의**:
1. `total_value = account.total_value(prices)`, `total_return = account.total_return(prices)`, `cash = account.cash`.
2. 종목별: `pnl, pnl_pct = account.position_pnl(sym, px)` (px = `prices.get(sym, h.avg_price)`). name 은 `account.history` 역순에서 해당 symbol 의 마지막 `name` (report.py 26–37행과 동일 규약, 헬퍼로 추출). `contribution = pnl` (전체 손익합의 부호별 크기).
3. `best`/`worst` = positions 중 pnl 최대/최소 (positions 없으면 None).
4. **MDD (journal 시계열)**: `equity_history` 의 `total` 시퀀스로
   - `data_sufficient = len(history) >= 2`.
   - 부족하면 `mdd=0.0`, `days_tracked=len(history)`, reasons 에 "자산 시계열 {n}일치뿐 — MDD·변동성은 데이터가 쌓이면 정확해집니다".
   - 충분하면 러닝 피크 대비 낙폭 최소값:
     ```
     peak = -inf; mdd = 0.0
     for t in totals:
         peak = max(peak, t)
         mdd = min(mdd, t/peak - 1.0)
     ```
5. **reasons (진단, 한국어)** — 다음을 조건부로 추가:
   - 전체: `f"총자산 {total_value:,.0f}원 · {total_return*100:+.2f}% (초기 대비)"`.
   - worst 종목: `f"가장 큰 손실: {worst.name} {worst.pnl_pct*100:+.1f}% ({worst.pnl:,.0f}원)"` (worst.pnl<0 일 때 "발목을 잡는 종목" 문구).
   - **섹터 집중 경고**: positions 종목들의 테마를 `trading.profile.themes.symbol_themes` 로 모아, 한 테마가 보유의 과반이면 `f"⚠️ 보유가 '{theme}' 테마에 {n}/{tot}종목 집중 — 섹터 동반 하락에 취약"`. (마스터 플랜 손실원인 1 진단)
   - 전 종목 손실이면: "보유 전 종목 평가손실 — 손절 규칙 부재 가능성(WP2에서 개선)".
   - data 부족 안내(위 4).

**추가 헬퍼** (report.py 중복 제거 겸용):
```python
def name_of(account: PaperAccount, symbol: str) -> str:
    """history 역순에서 종목 표시명을 찾는다(없으면 symbol)."""
```
report.py 34–37행과 app.py 236–237행이 이걸 재사용하도록 리팩터(선택이지만 권장, 동작 동일).

### 수정: `trading/paper/report.py`

`build_summary` 에 종목별 손익 표기 강화(현재도 보유종목 손익은 있음 — WP1은 "전체 진단 한 줄" 추가):
- 상단 총자산 줄 다음에, `analyze_performance` 의 `worst`/섹터경고 reasons 중 **최대 1줄**을 진단으로 추가:
  ```python
  # report.py 안에서 순환 import 피하려면 함수 내 지역 import
  from .analytics import analyze_performance
  perf = analyze_performance(account, prices, equity_history)
  # perf.reasons 중 '⚠️' 로 시작하거나 worst 관련 1줄만 append
  ```
- 시그니처 확장(하위호환): `build_summary(account, prices, period="일일", recent_trades=None, equity_history=None)`. `equity_history=None` 이면 기존과 동일 동작(진단 줄 생략). **watch.py 호출부는 `maybe_send_summary` 에서 `load_equity_history(storage)` 를 읽어 넘기도록 1줄 추가** (아래 접점).

### 접점 (watch.py)
`watch.py maybe_send_summary` 에서 요약 만들 때 equity_history 전달:
```python
from trading.paper import load_equity_history   # 이미 build_summary/record_snapshot import 중
eq = load_equity_history(storage)
notifier.send(build_summary(account, prices, "일일", today_trades, equity_history=eq))
# 주간도 동일하게 equity_history=eq 추가
```
watch.py 는 `record_snapshot` 을 매 루프 호출하므로 이 값이 존재. **인자 미전달 시에도 동작하므로 하위호환 안전.**

### 완료 기준
```bash
# journal 1행(현재)으로도 무에러
./venv/bin/python -c "
from trading.storage import get_storage
from trading.paper import PaperAccount, load_equity_history
from trading.paper.analytics import analyze_performance
s=get_storage('local'); acc=PaperAccount.from_dict(s.load_profile('_paper'))
prices={sym:h.avg_price for sym,h in acc.holdings.items()}
p=analyze_performance(acc, prices, load_equity_history(s))
print('return', round(p.total_return*100,2), 'mdd', p.mdd, 'suff', p.data_sufficient)
[print(' -',r) for r in p.reasons]"
# 요약에 진단 줄 포함
./venv/bin/python watch.py --once   # (텔레그램 없으면 콘솔로 출력) 에러 없이 요약 발송
```

---

## WP2: 매매 수식 개선 🎚️ (핵심)

**목표**: (a) 손절/트레일링 스탑 강제 청산, (b) 매도 판단에서 선호도 제외(재가중), (c) 실시간 환율(폴백), (d) 재진입 쿨다운. 모두 config 상수 사용 + reasons 근거.

### (c) 실시간 환율 — DataSource 경유

**수정**: `trading/data/base.py` — 추상 메서드 추가(기본 구현 제공해 다른 소스 하위호환):
```python
def get_fx(self, pair: str = "USD/KRW") -> float | None:
    """환율을 조회한다. 실패/미지원 시 None. 기본 구현은 None(선택 기능)."""
    return None
```
(추상 아닌 일반 메서드로 두어 기존/미래 소스가 강제 구현 안 해도 됨.)

**수정**: `trading/data/fdr_source.py` — 구현:
```python
@lru_cache(maxsize=1)
def _fx_cache_key(): ...  # 날짜별 1회 캐시 권장(과호출 방지)

def get_fx(self, pair: str = "USD/KRW") -> float | None:
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            df = fdr.DataReader(pair)
        return float(df["Close"].dropna().iloc[-1])
    except Exception:  # noqa: BLE001
        return None
```
→ **분석/전략 코드는 fdr 를 직접 import 하지 않는다.** trader 는 `data_source.get_fx()` 만 호출.

**수정**: `trading/paper/trader.py` — 고정환율 제거, 소스 경유 + 폴백:
```python
from ..config import FX_USD_KRW_FALLBACK, POSITION_PCT, STOP_LOSS_PCT, TRAILING_STOP_PCT, REENTRY_COOLDOWN_DAYS

def resolve_fx(data_source) -> float:
    """실시간 USD/KRW, 실패 시 폴백."""
    fx = data_source.get_fx("USD/KRW")
    return fx if fx and fx > 0 else FX_USD_KRW_FALLBACK

def to_krw(price: float, market: str, fx: float = FX_USD_KRW_FALLBACK) -> float:
    return price * fx if market == "US" else price
```
**하위호환**: `to_krw(price, market)` 2인자 호출(app.py 47행, 20행)이 남아 있으므로 `fx` 는 기본값 유지. `run_paper_trading` 시작부에서 `fx = resolve_fx(data_source)` 한 번 구해 루프에서 `to_krw(..., fx)` 로 넘긴다. **app.py `holding_prices` 도 `fx = data_src.get_fx('USD/KRW') or 1350` 로 개선(선택), 미변경 시 폴백으로 동작.**

### (b) 매도 판단에서 선호도 제외 — 재가중 공식

매수는 추세+뉴스+선호 그대로. **매도 판정용 별도 점수**를 선호 제외·재정규화로 만든다.

**수정**: `trading/signal/engine.py` — 새 함수(기존 `combine_scores` 불변):
```python
def reweight_without_pref(weights: dict[str, float]) -> dict[str, float]:
    """선호(pref) 가중치를 뺀 뒤 합이 1이 되도록 추세·뉴스를 재정규화한다.

    공식: w' = {trend: w_t/(w_t+w_n), news: w_n/(w_t+w_n), pref: 0.0}
    분모가 0이면(둘 다 0) 추세 100% 로 폴백.
    """
    wt, wn = weights.get("trend", 0.0), weights.get("news", 0.0)
    denom = wt + wn
    if denom <= 0:
        return {"trend": 1.0, "news": 0.0, "pref": 0.0}
    return {"trend": wt / denom, "news": wn / denom, "pref": 0.0}


def sell_score(trend: float, news: float,
               weights: dict[str, float] | None = None) -> SignalResult:
    """매도 판정용 종합점수: 선호 제외 재가중(추세·뉴스만)."""
    w = reweight_without_pref(weights or DEFAULT_WEIGHTS)
    return combine_scores(trend, news, 0.0, w)   # pref=0, 가중치도 0이라 무영향
```
예: 기본 50/30/20 → 매도판정은 trend 0.625 / news 0.375. 선호도 20%가 하락 종목을 떠받치던 구조 제거(손실원인 2).

**분리 활용**: `analyze_symbol` 반환 `Analysis` 에 매도용 점수를 담는다(하위호환 위해 필드 추가·기존 필드 유지):
- `Analysis` 에 `sell_signal: SignalResult` 필드 추가.
- `analyze_symbol` 끝에서 `sell_sig = sell_score(trend.score, news.score, weights)` 계산해 채운다.
- **기존 `signal` 필드·시그니처 불변** → 대시보드 종목분석 탭 영향 없음.

### (a) 손절 / 트레일링 스탑 + (d) 쿨다운 — trader 우선 청산 로직

**보유 메타 확장**: 트레일링용 고점·손절 쿨다운을 어디 저장? `PaperAccount` 를 건드리면 저장 스키마가 바뀐다. **하위호환 유지**하며 확장:

**수정**: `trading/paper/account.py`
- `Holding` 에 `peak_price: float = 0.0` 필드 추가(매수 시 avg_price 로 초기화, from_dict 는 `Holding(**h)` 라 없는 키는 기본값 → **구 데이터 무에러 로드**). `buy()` 에서 신규/추가매수 후 `h.peak_price = max(h.peak_price, price)`.
- `PaperAccount` 에 `cooldowns: dict[str, str] = field(default_factory=dict)` 추가(symbol -> 마지막 손절일 ISO date). `to_dict`/`from_dict` 에 `cooldowns` 직렬화 추가(`from_dict` 는 `data.get("cooldowns", {})` 로 구 데이터 호환).
- `sell()` 에 사유 인자: `sell(self, symbol, price, name="", reason="시그널")`. `_record` 에 `reason` 추가(dict 키 `reason`). 기존 호출 호환(기본값 "시그널").

**수정**: `trading/paper/trader.py` — `run_paper_trading` 매매 순서 재구성. **순서: 1)분석 → 2)트레일링 갱신 → 3)강제청산(손절/트레일) → 4)시그널 매도 → 5)시그널 매수(쿨다운 필터)**.

의사코드(정확한 판정):
```
fx = resolve_fx(data_source)
today = date.today().isoformat()
for sym in symbols:
    a = analyze_symbol(sym, profile, data_source, news_source, weights=weights)
    px = to_krw(a.price.last_close, a.price.market, fx)
    prices[sym] = px
    actions[sym] = (a.signal.action, a.sell_signal.action, a.price.name)  # 매수용/매도용 분리

# 2) 트레일링 고점 갱신 (보유 종목)
for sym, h in account.holdings.items():
    if sym in prices:
        h.peak_price = max(h.peak_price or h.avg_price, prices[sym])

# 3) 강제 청산 — 손절/트레일링 (시그널 무관)
for sym in list(account.holdings):
    if sym not in prices: continue
    h = account.holdings[sym]; px = prices[sym]
    down_from_avg  = px / h.avg_price - 1.0
    down_from_peak = px / (h.peak_price or h.avg_price) - 1.0
    if down_from_avg <= -STOP_LOSS_PCT:
        rec = account.sell(sym, px, name=..., reason=f"손절(-{STOP_LOSS_PCT:.0%})")
        account.cooldowns[sym] = today
    elif down_from_peak <= -TRAILING_STOP_PCT:
        rec = account.sell(sym, px, name=..., reason=f"트레일링(-{TRAILING_STOP_PCT:.0%})")
        account.cooldowns[sym] = today
    # rec 있으면 trades.append(rec)

# 4) 시그널 매도 — 선호 제외 매도점수 기준 (남은 보유 종목)
for sym,(buy_act, sell_act, name) in actions.items():
    if sym in account.holdings and sell_act == "매도":
        rec = account.sell(sym, prices[sym], name=name, reason="시그널(선호제외)")
        if rec: trades.append(rec)

# 5) 시그널 매수 — 미보유 + 매수시그널 + 쿨다운 경과
budget = account.initial_capital * POSITION_PCT
for sym,(buy_act, sell_act, name) in actions.items():
    if buy_act == "매수" and sym not in account.holdings:
        if in_cooldown(account.cooldowns.get(sym), today, REENTRY_COOLDOWN_DAYS):
            continue   # 손절 후 N영업일 내 재매수 금지
        rec = account.buy(sym, prices[sym], krw_amount=min(budget, account.cash), name=name)
        if rec: trades.append(rec)
```

**쿨다운 판정 헬퍼** (영업일 근사 — 캘린더 없이 numpy busday 사용):
```python
import numpy as np
def in_cooldown(last_sold_iso: str | None, today_iso: str, days: int) -> bool:
    """마지막 손절일로부터 영업일 days 이내면 True(재매수 금지)."""
    if not last_sold_iso:
        return False
    bdays = int(np.busday_count(last_sold_iso[:10], today_iso[:10]))
    return bdays < days
```
(주말은 자동 제외. 공휴일은 무시 — 근사로 충분, reasons 에 "영업일 기준" 명시.)

**reasons**: 강제청산 체결 rec 에는 `reason` 키가 있으므로 report/journal 에서 사유 노출. `run_paper_trading` 은 (trades, prices) 튜플 반환 유지(하위호환) — trades 각 dict 에 `reason` 포함되어 상위에서 활용.

### 접점 정리 (둘 다 동작 보장)
- **watch.py**: `run_paper_trading(account, profile, data_src, news_src, symbols)` 시그니처·반환 불변 → 수정 불필요. 단 `account.to_dict()` 에 `cooldowns`/`peak_price` 가 추가되어 저장됨(자동).
- **app.py**: `run_paper_trading(...)` 동일 호출. `to_krw` 2인자 호출 호환. 거래내역 expander 에 `reason` 컬럼 추가(선택): `r.get("reason","")`.

### 완료 기준
```bash
# 재가중 공식: 합=1, pref=0
./venv/bin/python -c "
from trading.signal.engine import reweight_without_pref
w=reweight_without_pref({'trend':0.5,'news':0.3,'pref':0.2}); print(w, round(sum(w.values()),6))"
# 손절 시나리오(순수 단위 테스트, 네트워크 불필요)
./venv/bin/python -c "
from trading.paper.account import PaperAccount
from trading.paper.trader import in_cooldown
acc=PaperAccount(); acc.buy('X',100,krw_amount=1000,name='X')
# 평단 100 → 현재가 90(-10%)면 손절 대상
h=acc.holdings['X']; px=90; print('down', px/h.avg_price-1)
print('cooldown', in_cooldown('2026-07-01','2026-07-03',3))"
# 실시간 환율(네트워크 필요, 실패 시 폴백 확인)
./venv/bin/python -c "from trading.data import get_source; print(get_source('fdr').get_fx('USD/KRW'))"
# 파이프라인 + 모의 1회
./venv/bin/python -c "from trading.data import get_source; from trading.analysis import trend_score; p=get_source('fdr').get_price('005930','2023-01-01'); print(trend_score(p.df).score)"
./venv/bin/python watch.py --once
```

---

## WP3: 가중치·임계값 튜닝 — 느낌 말고 숫자로

**목표**: `buy_th × sell_th × 손절률` 그리드서치를 유니버스 전 종목 × 최근 3년으로 돌려 종목별·평균 CAGR/MDD/Sharpe/승률 표 산출 → 최적 조합을 수치 근거와 함께 제시 → config 갱신.

### 백테스트 엔진 확장: `trading/backtest/engine.py`

`run_backtest` 에 손절 파라미터 추가(하위호환 — 기본 None=손절 없음, 기존 호출 불변):
```python
def run_backtest(df, score_series=None, buy_th=None, sell_th=None,
                 fee=None, stop_loss=None) -> BacktestResult:
```
- `buy_th/sell_th/fee` None → config 기본값(WP0).
- `stop_loss`(예 0.08) 주면 **손절을 백테스트에도 반영**(모의투자와 일관):
  - 포지션 진입가 추적 후, 보유 중 `close/entry - 1 <= -stop_loss` 인 날 강제 청산(다음 날부터 현금). look-ahead 유지: 손절 판정은 t일 종가 → t+1 청산.
  - 구현: 벡터화가 까다로우면 진입일부터의 최저 수익률을 순회 계산하는 루프 허용(유니버스 ~10 × 3년 ≈ 750행 × 수십 조합 → 충분히 빠름).
  - `BacktestResult` 에 `stop_loss: float | None = None` 필드 추가(summary 에 표기).

### 신설: `trading/backtest/gridsearch.py`

```python
"""임계값·손절률 그리드서치 (WP3).

운용 유니버스 전 종목 × 최근 N년으로 (buy_th, sell_th, stop_loss) 조합을 백테스트하고
종목 평균 지표로 순위를 매긴다. DataSource 경유(FinanceDataReader 직접 import 금지).
"""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from ..data.base import DataSource
from .engine import run_backtest

# 그리드 (조합 수 억제: 4 × 4 × 3 = 48 조합)
BUY_GRID   = [55, 60, 65, 70]
SELL_GRID  = [35, 40, 45, 50]
STOP_GRID  = [None, 0.08, 0.12]
```

```python
@dataclass
class GridResult:
    buy_th: float
    sell_th: float
    stop_loss: float | None
    avg_cagr: float
    avg_mdd: float
    avg_sharpe: float
    avg_win_rate: float
    avg_beats_bnh: float       # B&H 이긴 종목 비율
    per_symbol: dict            # symbol -> (cagr, mdd, sharpe, win_rate)


def run_grid(symbols: list[str], data_source: DataSource,
             start: str = "2023-01-01",
             buy_grid=BUY_GRID, sell_grid=SELL_GRID, stop_grid=STOP_GRID
             ) -> list[GridResult]:
    """유니버스 각 종목의 가격을 1회 로드(캐시)하고 모든 조합을 백테스트한다."""
    # 1) 종목별 가격 df 를 한 번만 로드 (조합마다 재로드 금지 — 속도)
    price_cache = {}
    for s in symbols:
        try: price_cache[s] = data_source.get_price(s, start=start).df
        except Exception: continue    # 실패 종목 skip
    results = []
    for b in buy_grid:
        for sl in sell_grid:
            if sl >= b: continue       # 매도선 >= 매수선 이면 무의미, 스킵
            for st in stop_grid:
                per = {}
                for s, df in price_cache.items():
                    r = run_backtest(df, buy_th=b, sell_th=sl, stop_loss=st)
                    per[s] = (r.cagr, r.mdd, r.sharpe, r.win_rate, r.beats_bnh)
                results.append(_aggregate(b, sl, st, per))
    return results
```

**평가 기준 / 랭킹**:
- 1차 정렬: `avg_sharpe` 내림차순(위험조정수익 우선).
- 동점 시: `avg_mdd` 큰 값(=덜 깊은 낙폭) 우선 → `avg_cagr` 내림차순.
- **필터**: `avg_mdd >= -0.35` (MDD 35% 초과 조합 제외 — 마스터 플랜의 "MDD 크다" 문제 정면 대응). 필터 통과 조합 없으면 필터 완화 후 재선정하고 문서에 명시.
- `avg_beats_bnh` 는 참고 지표로 표에 병기.

### 실행 스크립트 + 산출물 저장

**신설**: `scripts/run_gridsearch.py` (또는 `trading/backtest/gridsearch.py` 하단 `if __name__ == "__main__"`):
```python
# 유니버스 = 현재 프로필 target_universe (없으면 반도체 대표 등 폴백 ~10종목)
# run_grid 실행 → 상위 10 조합 표 + 종목별 표를 docs/tuning-result.md 로 Write
# 최적 조합을 print (config 갱신 근거)
```
저장 위치: `docs/tuning-result.md` (표 + 채택 근거). 원자료 필요 시 `data_store/_gridsearch.json`.

**config 갱신**: 최적 (buy_th, sell_th, stop_loss) 로 `trading/config.py` 의 `BT_BUY_TH`/`BT_SELL_TH`/`STOP_LOSS_PCT` 갱신. 종합점수 임계값(BUY/SELL_THRESHOLD)은 추세 임계값과 스케일이 다르므로(추세 단일 vs 종합 가중합) **직접 대입 금지** — 문서에 "백테스트는 추세 점수, 실운용은 종합점수라 임계값 축이 다름. 종합 임계값은 추세 최적선을 참고해 보수적으로 설정" 명시하고 잠정 통일값 유지/미세조정.

**속도 가드**: 유니버스 10종목 × 48조합 = 480 백테스트, 가격은 종목당 1회만 로드(캐시). 3년≈750행 벡터연산 → 수십 초 내. 손절 루프 있어도 종목당 750행이라 부담 적음.

### 완료 기준
```bash
# 소규모 스모크(2종목 × 축소 그리드)로 동작 확인 — 네트워크 필요
./venv/bin/python -c "
from trading.data import get_source
from trading.backtest.gridsearch import run_grid
res=run_grid(['005930','000660'], get_source('fdr'), buy_grid=[60,65], sell_grid=[40,45], stop_grid=[None,0.08])
res=[r for r in res if r.avg_mdd>=-0.35] or res
top=sorted(res, key=lambda r:(-r.avg_sharpe, r.avg_mdd, -r.avg_cagr))[0]
print('BEST', top.buy_th, top.sell_th, top.stop_loss, 'sharpe', round(top.avg_sharpe,2), 'mdd', round(top.avg_mdd*100,1))"
# 전체 실행 + 문서 생성
./venv/bin/python scripts/run_gridsearch.py && head -30 docs/tuning-result.md
```

---

## WP4: 자산추이 그래프 분석 📈 (대시보드)

**목표**: `app.py` 모의투자 탭에 (1) journal 기반 자산곡선+드로다운, (2) 종목별 손익 기여 막대, (3) WP1 분석 리포트 표시. journal 1행이어도 무에러.

### 수정: `app.py` 모의투자 탭 (tab_paper, 183행 이후)

기존 자산곡선 블록(214–228행) 확장:
1. **자산곡선 + 드로다운** (journal `total` 사용):
   - `eq_hist = load_equity_history(storage)`.
   - `len>=2` 이면: 상단 subplot 총자산 area, 하단 subplot 드로다운(러닝피크 대비 %). Plotly `make_subplots(rows=2, shared_xaxes=True)` 또는 두 개 차트.
   - `len<2` 이면 기존 안내 문구 유지("2일 이상 쌓이면 표시").
2. **WP1 분석 리포트**:
   ```python
   from trading.paper.analytics import analyze_performance
   perf = analyze_performance(account, prices, eq_hist)
   st.markdown("**📊 성과 진단**")
   c=st.columns(3)
   c[0].metric("MDD(누적)", f"{perf.mdd*100:.1f}%" if perf.data_sufficient else "—")
   c[1].metric("추적 일수", perf.days_tracked)
   c[2].metric("보유 종목", len(perf.positions))
   for r in perf.reasons: st.write(f"- {r}")   # ⚠️ 섹터집중·최대손실 등 근거 노출
   ```
3. **종목별 손익 기여 막대** (positions):
   ```python
   if perf.positions:
       import plotly.graph_objects as go
       names=[p.name for p in perf.positions]; pnls=[p.pnl for p in perf.positions]
       colors=['#E74C3C' if v<0 else '#27AE60' for v in pnls]
       bar=go.Figure(go.Bar(x=names, y=pnls, marker_color=colors))
       bar.update_layout(height=280, yaxis_title="평가손익(원)", margin=dict(t=10,b=10))
       st.plotly_chart(bar, use_container_width=True)
   ```
4. 거래내역 expander(245–252행)에 `reason` 컬럼 추가: `"사유": r.get("reason","")`.

**접점**: `holding_prices`/`prices` 재사용(이미 있음). `analyze_performance` 는 순수 계산이라 캐시 불필요. 종목분석 탭·백테스트 탭·watch.py 는 손대지 않음.

### 완료 기준
```bash
# import·구문 검증 (Streamlit 실행 없이)
./venv/bin/python -c "import ast; ast.parse(open('app.py').read()); print('app.py OK')"
./venv/bin/python -c "from trading.paper.analytics import analyze_performance; print('ok')"
# 수동: ./venv/bin/streamlit run app.py → 모의투자 탭에서 자산곡선/드로다운/기여막대/진단 렌더 확인
```

---

## 전체 완료 기준 (마스터 플랜 대응)
1. 파이프라인 점검 통과: `./venv/bin/python -c "from trading.data import get_source; from trading.analysis import trend_score; p=get_source('fdr').get_price('005930','2023-01-01'); print(trend_score(p.df).score)"`
2. `./venv/bin/python watch.py --once` 가 새 수식(손절·선호제외 매도·실시간환율·쿨다운)으로 동작.
3. `docs/tuning-result.md` 에 튜닝 수치 표 + 채택 근거, `trading/config.py` 갱신.
4. 대시보드 모의투자 탭에서 자산곡선·드로다운·기여막대·진단 리포트 렌더.
5. journal 1행 상태에서도 WP1/WP4 무에러(데이터 축적 중 안내).

## 하위호환 체크리스트 (watch.py + 대시보드 둘 다 동작)
- `combine_scores`/`decide_action`/`analyze_symbol` 시그니처 불변(필드만 추가).
- `run_paper_trading` (trades, prices) 반환·인자 불변.
- `to_krw` 2인자 호출 호환(fx 기본값).
- `PaperAccount.from_dict` 구 JSON(`peak_price`/`cooldowns`/`reason` 없음) 무에러 로드.
- `run_backtest(ind, buy_th=…, sell_th=…, fee=…)` app.py 호출 불변(신규 인자 기본 None).
- `build_summary(..., equity_history=None)` 미전달 시 기존 동작.
