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
    (예정) profile/           ← 사용자 선호 카테고리 가중치 (3단계)
    (예정) signal/            ← 트렌드+뉴스+선호 종합 시그널 (4단계)
    (예정) backtest/          ← 백테스팅 엔진 (5단계)
    (예정) paper/             ← 모의투자 가상 계좌 (6단계)
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
- [ ] **3단계: 사용자 선호 카테고리** — 반도체/2차전지/배당 등 가중치 프로필
- [ ] **4단계: 종합 시그널 엔진** — 트렌드+뉴스+선호 → 매수/매도 점수
- [ ] **5단계: 백테스팅** — 과거 데이터로 전략 검증 (수익률·MDD·승률)
- [ ] **6단계: 모의투자** — 가상 계좌 시뮬레이션 + 대시보드 통합

## 코딩 컨벤션
- 데이터 접근은 `trading/data`의 `DataSource`를 통해서만. 분석 코드에서 `FinanceDataReader` 직접 import 금지.
- 점수 산출 함수는 **근거(reasons) 리스트를 함께 반환**한다 (사용자에게 "왜 이 점수인지" 설명).
- 새 분석 모듈은 0~100 점수 + 근거 패턴을 따른다.
- 주석·UI 문구는 한국어. 코드 식별자는 영어.
- 비밀키·API 키는 `.env`로 분리, 절대 커밋하지 않는다.
- 실거래 관련 코드는 사용자 명시 승인 전까지 추가하지 않는다 (안전 규칙 1).

## 직접 해야 하는 일 (코드 밖)
- [ ] (2단계) 뉴스 API/RSS 소스 선택 및 (필요 시) 키 발급
- [ ] (4단계 이후) 전략 가중치를 백테스팅 결과 보고 함께 결정
- [ ] (실거래 전환 시, 먼 미래) 증권사 OpenAPI 계좌·인증 — 충분한 검증 후에만
