# TODO

## 🔴 지금 할 일 (보안)
- [ ] **노출된 GitHub PAT 폐기** — 채팅에 평문 노출됨. [Settings → Tokens](https://github.com/settings/tokens)에서 Revoke
- [ ] 새 토큰 발급 후 `gh auth login` 으로 영구 로그인 → 다음부터 `git push`만으로 됨

## 📲 텔레그램 알림 연결 (5단계 마무리)
- [ ] `@BotFather` → `/newbot` → 봇 토큰 발급
- [ ] `cp .env.example .env` 후 `TELEGRAM_BOT_TOKEN` 입력
- [ ] 봇에게 메시지 1회 전송 → `./venv/bin/python watch.py --get-chat-id` → `TELEGRAM_CHAT_ID` 입력
- [ ] 대시보드에서 관심종목 ⭐ 즐겨찾기 등록
- [ ] `./venv/bin/python watch.py` 로 실제 알림 수신 테스트

## 🚧 다음 개발 단계
- [ ] **5.5단계: 백테스팅** — 시그널이 과거에 실제로 통했는지 검증 (수익률·MDD·승률). 가중치 튜닝의 근거
- [ ] **6단계: 24시간 배포** — Oracle Cloud 무료 VM 등 always-on 호스팅에서 watch.py 상시 구동
- [ ] (추후) 모의투자 가상 계좌 시뮬레이션
- [ ] (먼 미래, 명시 승인 후) 증권사 OpenAPI 실거래 — 백테스팅 충분히 검증 후에만

## ✅ 완료 (1~5단계)
- [x] 1단계: 데이터 소스 추상화 + 트렌드 분석(MA/RSI/MACD) + Streamlit 대시보드
- [x] 2단계: 뉴스 호재 분석 (구글 뉴스 RSS + 키워드 점수)
- [x] 3단계: 사용자 선호 카테고리 (테마 가중치 + 즐겨찾기, 로컬 JSON 저장소)
- [x] 4단계: 종합 시그널 엔진 (추세50:뉴스30:선호20 → 매수/관망/매도)
- [x] 5단계: 24시간 감시 워커 + 텔레그램 알림 (중복방지)
- [x] GitHub 비공개 레포 연결 + 푸시
