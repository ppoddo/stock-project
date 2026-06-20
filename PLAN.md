# PLAN — 레퍼런스 비교 & 로드맵

> 2026-06-20 작성. 오픈소스 트레이딩 봇·호스팅·백테스팅·뉴스감성 레퍼런스를 조사해
> 우리 프로젝트와 비교하고, 우선순위 체크리스트로 정리했다.

---

## 1. 조사한 레퍼런스

| 프로젝트 | 특징 | 우리가 참고할 점 |
|---------|------|----------------|
| [intelligent-trading-bot](https://github.com/asavinov/intelligent-trading-bot) | ML 시그널 + **텔레그램 알림 채널** + feature engineering | 텔레그램 시그널 봇 구조·확장 feature 설계 |
| [stock-market-alert-bot](https://github.com/oleiameliengan/stock-market-alert-bot) | **Streamlit + RSI/MACD/VWAP + paper-trade 알림** (Alpaca) | 우리와 가장 유사 — 모의투자 알림 흐름 |
| [aruancaf/stock-trading-bot](https://github.com/aruancaf/stock-trading-bot) | EMA 크로스·돌파 + **뉴스 감성** 결합 매수/매도 | 시그널 결합 방식 |
| [awesome-systematic-trading](https://github.com/wangzhe3224/awesome-systematic-trading) | 퀀트 라이브러리·전략 큐레이션 | 백테스팅·지표 라이브러리 선택 |
| [ProsusAI/finBERT](https://github.com/ProsusAI/finBERT) | 금융 특화 감성분석 BERT | 뉴스 점수 고도화 경로 |

**핵심 인사이트**
- **호스팅**: Fly.io·Railway는 2024~2026 무료 티어 폐지. **Oracle Cloud Free Tier(ARM 4 OCPU·24GB·평생 무료)** 가 24시간 무인 봇의 사실상 표준. systemd로 자동재시작.
- **백테스팅 지표**: 수익률(CAGR)·**MDD(최대낙폭)**·**Sharpe(위험조정수익)**·승률이 4대 지표. 함정 = look-ahead bias, 과최적화, 비현실적 수수료 가정. 라이브러리: `backtesting.py`(초보 친화) / `vectorbt`(고속).
- **뉴스 감성**: 키워드(Loughran-McDonald 사전) < FinBERT < LLM(GPT-4o/Claude few-shot) 순으로 정확. 한국어는 KorFinASC 등. → 우리 키워드 방식은 좋은 출발점, 다음은 **Claude LLM** 또는 FinBERT.

---

## 2. 우리 프로젝트 vs 레퍼런스

### ✅ 우리가 이미 잘한 것 (레퍼런스보다 나은 점)
- **소스 추상화** (데이터·뉴스·저장소·알림 전부 인터페이스) — 대부분 오픈소스 봇은 라이브러리 직접 결합
- **설명가능성**: 0~100 점수 + **근거(reasons)** 동반 — 대부분 봇은 블랙박스
- **한/미 통합** 데이터·뉴스
- **중복 알림 방지**(상태 변화 시에만) — 의외로 빠진 봇 많음
- **안전 규칙 명문화**(실거래 금지/참고용 고지)

### ⚠️ 부족한 것 (개선 기회)
1. **24시간 배포** — 현재 로컬 전용. 컴퓨터 꺼지면 멈춤 ← **사용자 최우선**
2. **백테스팅·리스크 지표** — 시그널이 과거에 통했는지 미검증 (MDD/Sharpe/승률 없음)
3. **뉴스 감성 정밀도** — 키워드 기반(영어 매칭률 낮음). LLM/FinBERT 미적용
4. **모의투자(paper)** — 가상 계좌·수익률 추적 없음
5. **종목 유니버스** — 즐겨찾기만 감시. 테마 전체 스캔으로 "새 매수 후보 발굴" 불가
6. **장 시간 인지** — 장 마감 후에도 동일 점검(불필요 호출)
7. **테스트/CI 없음** — sticker 프로젝트엔 있었음 (pytest + lint)

---

## 3. 우선순위 체크리스트

### 🅰️ 지금 — 24시간 무인 운영 (사용자 최우선)
- [ ] **텔레그램 연결** (사용자 진행 중): 봇 토큰 → `.env` → chat_id → 즐겨찾기 → `watch.py` 테스트
- [ ] **Oracle Cloud Free 계정 생성** (ARM Ampere A1, 평생 무료)
- [ ] VM에 Python 3.12 + 레포 클론 + venv 세팅
- [ ] **systemd 서비스 등록** (`watch.service`) → 부팅 시 자동시작·크래시 자동재시작
- [ ] `journalctl` 로 로그 확인 + `.env` 를 서버에 안전 배치
- [ ] (코드) **장 시간 인지** 추가 — KR 09:00~15:30 / US 장 시간에만 점검(주말·공휴일 skip)
- [ ] (코드) `WATCH_INTERVAL_MIN` 장중 짧게/장외 길게 분리 옵션

### 🅱️ 신뢰성 — 백테스팅으로 검증 (배포 다음)
- [ ] `trading/backtest/` 엔진 추가 (소스 추상화 재사용)
- [ ] 4대 지표 산출: **CAGR · MDD · Sharpe · 승률**
- [ ] 단순 룰부터: "종합점수 ≥ 70 매수 / < 40 매도" 를 과거 데이터로 검증
- [ ] look-ahead bias 차단(당일 종가로 당일 판단 금지), 수수료·슬리피지 가정 반영
- [ ] 결과 보고 **세 점수 가중치(추세50:뉴스30:선호20) 튜닝** — "느낌" 금지(안전규칙4)
- [ ] 대시보드에 백테스트 결과 탭 추가

### 🅲️ 고도화 — 정밀도·기능 (그 후 천천히)
- [ ] **뉴스 감성 LLM 업그레이드**: 키워드 → Claude API(few-shot) 또는 FinBERT (`notify`처럼 소스 교체식)
- [ ] **테마 전체 스캔**: 즐겨찾기 외 테마 종목까지 훑어 "새 매수 후보" 알림
- [ ] **모의투자 가상계좌** (`trading/paper/`): 시그널로 가상 매매 → 수익률 추적
- [ ] 가격 급변동/거래량 급증 별도 알림
- [ ] **pytest + GitHub Actions CI** (점수 함수·중복방지 회귀 테스트)
- [ ] 배포 저장소를 로컬 JSON → **Supabase**로 교체(휘발성 대비) — 이미 `Storage` 추상화됨

### 🅳️ 먼 미래 (명시 승인 후에만)
- [ ] 증권사 OpenAPI 실거래 — 백테스팅·모의투자로 충분히 검증된 뒤에만 (안전규칙1)

---

## 4. 추천 진행 순서
1. **텔레그램 연결** → 로컬에서 알림 동작 확인 (오늘)
2. **Oracle Cloud 배포 + systemd** → 컴퓨터 꺼져도 24시간 (사용자 목표 달성)
3. **백테스팅** → 가중치/임계값을 숫자로 검증 (신뢰 확보)
4. 이후 🅲 항목을 필요 순서대로

> 원칙: 배포로 "계속 돌게" 먼저 만들고, 백테스팅으로 "믿을 만하게" 만든 뒤, 고도화한다.
