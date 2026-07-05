---
name: retro
description: 손익 회고 → 데이터 기반 개선 루프 — 체결·저널에서 손실 패턴을 찾고, 개선 가설을 백테스트 수치로 검증해서 증명된 것만 채택. "왜 자꾸 잃냐", "전략 개선해줘", "회고하자" 요청 시 사용.
---

# 손실 회고 → 검증된 개선 (/retro)

## 철학 (CLAUDE.md 안전규칙 4 — 이 스킬의 존재 이유)
**느낌으로 파라미터를 바꾸지 않는다.** 손해는 데이터다 — 패턴을 찾고, 가설을 세우고,
백테스트 수치(CAGR·MDD·Sharpe·승률)로 현행 대비 개선이 **증명된 변경만** 채택한다.
증명 못 한 가설은 "기각"으로 기록하고 버린다. 그것도 성과다.

## 절차
1. **데이터 수집** (VM이 원본):
```bash
ssh oracle-vm "cd stock-project && cat data_store/_paper.json" > /tmp/paper.json
ssh oracle-vm "cd stock-project && cat data_store/_equity.json" > /tmp/equity.json
```
2. **손실 패턴 분석** — 최소 다음을 계산:
   - 매도 사유별(시그널/손절/트레일링) 건수·평균 손익 — 손절이 실제로 손실을 줄였나?
   - 종목·테마별 손익 기여 — 특정 섹터가 계속 깎아먹나?
   - 재매수 후 재손절(왕복 손실) 발생 여부 — 쿨다운이 충분한가?
   - 보유기간 분포 — 너무 빨리 팔거나 너무 오래 버티나?
3. **가설 수립** (1~3개, 구체적 파라미터로): 예) "손절 -8%가 너무 타이트 → -10~-12% 비교",
   "매도 임계 35가 늦음 → 40 비교", "쿨다운 3→5영업일".
4. **검증** — 유니버스 전 종목 × 최근 3년, 현행 vs 가설 나란히:
   - 그리드서치: `./venv/bin/python scripts/run_gridsearch.py` (범위는 스크립트 안에서 조정)
   - 단일 비교: `run_backtest(df, buy_th=…, sell_th=…, stop_loss=…)` 로 표 작성
5. **채택/기각 결정** — 판단 기준: Sharpe 우선, MDD 얕은 순, CAGR. 차이가 근소하면 MDD 얕은 쪽(안전규칙4 정신).
6. **반영** — 채택 시에만:
   - `trading/config.py` 값 변경 + 주석에 근거 요약
   - `docs/tuning-result.md` 에 비교표·채택/기각 사유 **누적** (기존 내용 삭제 금지 — 히스토리가 자산)
   - `bash scripts/check.sh` 통과 확인
7. **배포는 사용자 확인 후** — 변경 요약과 근거 표를 보여주고 승인받으면 deploy 스킬 절차로.

## 가드레일
- 검증 표 없이 `trading/config.py` 를 바꾸는 것 금지.
- **종합점수 임계값(BUY/SELL_THRESHOLD)에 백테스트 추세 임계값(BT_*)을 직접 대입 금지** — 점수 스케일이 다름 (docs/tuning-result.md 참고).
- 백테스트 수정 시 t+1 체결(look-ahead 금지) 유지 — tests/test_backtest.py 가 지킨다.
- 실거래 코드 금지 (안전규칙 1).
