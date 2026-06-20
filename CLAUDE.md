# AI 트레이딩 어시스턴트 - 프로젝트 컨텍스트

## 앱 개요
시장 트렌드 · 뉴스 호재 · 사용자 선호 카테고리를 종합해 **주식/ETF 매수·매도 시그널**을
산출하고, 백테스팅·모의투자로 검증하는 개인용 트레이딩 어시스턴트.

- **대상 시장**: 한국(KRX) + 미국 — 데이터 소스를 추상화해 둘 다 지원
- **초기 단계**: 백테스팅 + 모의투자 (실거래 아님)
- **참고서**: 『파이썬을 이용한 알고리즘 트레이딩』 (전략/백테스팅 설계 참고)

## ⚠️ 최우선 안전 규칙 (돈이 걸린 프로젝트)
1. **실거래(실제 주문) 코드는 명시적 승인 없이는 절대 추가하지 않는다.** 현재는 백테스팅·모의투자 전용.
2. 증권사 API 키·계좌 정보는 **절대 코드/저장소에 넣지 않는다.** `.env` + `.gitignore`.
3. 시그널은 **참고용**이다. 모든 출력에 "투자 판단·책임은 사용자 본인" 전제를 깔고 만든다.
4. 전략 성과는 반드시 **백테스팅 수치(수익률·MDD·승률)**로 검증한 뒤 신뢰한다. "느낌"으로 가중치 바꾸지 않는다.

## 기술 스택
| 영역 | 기술 | 비고 |
|------|------|------|
| 언어 | Python 3.12 | venv 사용 (`./venv`) |
| 데이터 | FinanceDataReader | 한/미 주가·ETF 통합. 소스 추상화됨 |
| 분석 | pandas, numpy | 지표·점수 계산 |
| 웹 | Streamlit | 대시보드 |
| 시각화 | Plotly | 캔들·지표 차트 |
| 뉴스 | requests, feedparser, beautifulsoup4 | 구글 뉴스 RSS (키 불필요) |
| 백테스팅 | (예정) 자체 엔진 + 책 전략 | 5단계 |

## 폴더 구조
```
stock-project/
  app.py                      ← Streamlit 대시보드 진입점
  requirements.txt
  CLAUDE.md
  venv/                       ← 가상환경 (커밋 안 함)
  trading/
    data/                     ← 데이터 소스 (추상화 계층)
      base.py                 ← DataSource 인터페이스 + PriceData
      fdr_source.py           ← FinanceDataReader 구현
      __init__.py             ← get_source(name) 팩토리
    analysis/
      trend.py                ← 트렌드 지표(MA/RSI/MACD) + 0~100 추세 점수
    news/                     ← 뉴스 수집 + 호재 점수
      base.py                 ← NewsSource 인터페이스 + NewsItem
      google_news.py          ← 구글 뉴스 RSS 구현 (한/미 통합)
      sentiment.py            ← 키워드 기반 0~100 호재 점수
      __init__.py             ← get_news_source(name) 팩토리
    profile/                  ← 사용자 선호 카테고리
      themes.py               ← 투자 테마 정의 + 종목 매핑
      profile.py              ← UserProfile + 0~100 선호도 점수
    storage/                  ← 저장소 (추상화 계층)
      base.py                 ← Storage 인터페이스
      local.py                ← 로컬 JSON 구현 (배포 시 Firebase/Supabase로 교체)
    signal/                   ← 종합 시그널 엔진
      engine.py               ← 세 점수 가중합 → 매수/관망/매도 + analyze_symbol() 공용 진입점
    notify/                   ← 알림 채널 (추상화)
      base.py                 ← Notifier 인터페이스
      telegram.py             ← 텔레그램 봇 / console.py ← 콘솔 대체
    monitor/                  ← 감시 워커
      watcher.py              ← 즐겨찾기 순회 + 시그널 + 중복방지 알림
    backtest/                 ← 백테스팅 엔진
      engine.py               ← 추세 점수 전략 시뮬레이션 + CAGR/MDD/Sharpe/승률
    paper/                    ← 모의투자 (가상계좌 자동운용)
      account.py              ← PaperAccount (현금/보유/거래기록, 한·미 원화환산)
      trader.py               ← 시그널 → 자동 매수/매도 + 포지션 사이징(종목당 20%)
      report.py               ← 일일/주간 요약 리포트 (텔레그램 HTML)
  watch.py                    ← 24시간 모의투자 자동운용 + 요약발송 (--once / --get-chat-id)
```

## 개발 환경
```bash
# 의존성 설치
./venv/bin/pip install -r requirements.txt

# 웹 대시보드 실행
./venv/bin/streamlit run app.py    # localhost:8501

# 파이프라인 빠른 점검 (웹 없이)
./venv/bin/python -c "from trading.data import get_source; from trading.analysis import trend_score; \
  p=get_source('fdr').get_price('005930','2023-01-01'); print(trend_score(p.df).score)"
```
WSL Ubuntu에서 개발.

## 아키텍처 주의사항
### 데이터 소스 추상화 (핵심 설계)
모든 데이터 접근은 `trading/data/base.py`의 `DataSource` 인터페이스를 거친다.
분석·전략·시그널 코드는 **구체적 라이브러리(FinanceDataReader)를 직접 import 하지 않는다.**
→ 나중에 증권사 API로 교체해도 전략 코드는 그대로 둔다.

### 시장 자동 판별
종목코드 6자리 숫자 = 한국(KR), 그 외 = 미국(US)으로 추정 (`detect_market`).
한/미가 겹치는 코드 체계는 없어 현재는 충분하나, 확장 시 명시적 시장 지정 인자 고려.

### 점수 체계
- 트렌드/뉴스/선호 모두 **0~100 점수**로 통일해 4단계 시그널에서 가중합한다.
- 가중치는 5단계 백테스팅으로 튜닝한다. 그 전엔 동일 가중·투명하게 유지.

## 개발 단계 현황
- [x] **1단계: 데이터 + 트렌드 분석** — 한/미 수집, MA/RSI/MACD, 추세 점수, Streamlit 골격
- [x] **2단계: 뉴스 호재 분석** — 구글 뉴스 RSS 수집 + 키워드 기반 호재 점수, 종목명 자동조회, 대시보드 연결
- [x] **3단계: 사용자 선호 카테고리** — 테마 가중치 + 즐겨찾기, 0~100 선호도 점수, 로컬 JSON 저장소(추상화), 대시보드 연결
- [x] **4단계: 종합 시그널 엔진** — 세 점수 가중합(기본 추세50:뉴스30:선호20) → 매수/관망/매도, analyze_symbol() 공용 진입점, 대시보드 연결
- [x] **5단계: 24시간 감시 워커 + 텔레그램 알림** — 즐겨찾기 순회 → 시그널(매수/매도) 변화 시에만 텔레그램/콘솔 알림(중복방지), watch.py CLI
- [x] **5.5단계: 백테스팅** — 추세 점수 전략 시뮬레이션(CAGR·MDD·Sharpe·승률), Buy&Hold 비교, 대시보드 탭. ※뉴스·선호는 과거 재현 불가로 제외(트렌드만)
- [x] **모의투자 자동운용** — 가상 1천만원, 시그널 따라 자동 매수/매도(종목당 20% 분산), 한·미 원화환산, 일일/주간 텔레그램 요약, 대시보드 모의투자 탭
- [ ] **6단계: 24시간 배포** — Oracle 무료 VM 등 always-on 호스팅 (watch.py 상시 구동)

> 운영 목표(사용자 결정): **모의투자 자동운용 + 일일/주간 텔레그램 요약**. 실시간 매수/매도 알림 대신 정기 리포트. 실거래는 충분한 검증 후 명시 승인 시에만(안전규칙1).
> 모의투자 통화: 미국 종목은 고정환율(1,350원/$)로 원화 환산. TODO: 실시간 환율(`fdr.DataReader('USD/KRW')`).

## 코딩 컨벤션
- 데이터 접근은 `trading/data`의 `DataSource`를 통해서만. 분석 코드에서 `FinanceDataReader` 직접 import 금지.
- 점수 산출 함수는 **근거(reasons) 리스트를 함께 반환**한다 (사용자에게 "왜 이 점수인지" 설명).
- 새 분석 모듈은 0~100 점수 + 근거 패턴을 따른다.
- 주석·UI 문구는 한국어. 코드 식별자는 영어.
- 비밀키·API 키는 `.env`로 분리, 절대 커밋하지 않는다.
- 실거래 관련 코드는 사용자 명시 승인 전까지 추가하지 않는다 (안전 규칙 1).

## 직접 해야 하는 일 (코드 밖)
- [ ] (5단계) 텔레그램 봇 토큰 발급(@BotFather) → `.env` 입력 → `python watch.py --get-chat-id` 로 chat_id 확인 → `.env` 입력
- [ ] (6단계) 24시간 호스팅 선택 (Oracle 무료 VM 등) 후 watch.py 상시 구동
- [ ] (5.5단계 이후) 전략 가중치를 백테스팅 결과 보고 함께 결정
- [ ] (실거래 전환 시, 먼 미래) 증권사 OpenAPI 계좌·인증 — 충분한 검증 후에만

## 환경변수 (.env)
`.env.example` 참고. `.env` 는 커밋 금지(`.gitignore` 처리, `!.env.example` 예외).
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — 텔레그램 알림. 없으면 콘솔로 자동 대체.
- `WATCH_INTERVAL_MIN` — 감시 주기(분), 기본 30.

## 실행
- 대시보드: `./venv/bin/streamlit run app.py`
- 감시 워커: `./venv/bin/python watch.py` (무한) · `--once`(1회) · `--get-chat-id`(chat_id 확인)
