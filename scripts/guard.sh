#!/usr/bin/env bash
# AI 실수 방지 가드 — 빠른 정적 검사 (편집 훅 + check.sh 공용).
# 위반 시 exit 2 + 사유를 stderr 로 출력한다 (Claude Code 훅이 모델에게 피드백).
cd "$(dirname "$0")/.." || exit 0
fail=0
violation() { echo "🚫 GUARD 위반: $1" >&2; fail=2; }

# 1) 데이터 추상화(CLAUDE.md): FinanceDataReader 직접 import 는 trading/data/ 안에서만
hits=$(grep -rn --include='*.py' -E '^[^#]*(import FinanceDataReader|from FinanceDataReader)' \
       trading watch.py app.py 2>/dev/null | grep -v '^trading/data/')
[ -n "$hits" ] && violation "FinanceDataReader 직접 import (trading/data 밖 금지 — DataSource 추상화 경유):
$hits"

# 2) 안전규칙1: 실거래(증권사 주문 API) 코드는 명시 승인 전 금지
hits=$(grep -rniE --include='*.py' \
       'koreainvestment|kiwoom|creon|ebest|ls-sec|place_order|submit_order|주문[ _]?실행|실거래[ _]?주문' \
       trading watch.py app.py 2>/dev/null)
[ -n "$hits" ] && violation "실거래(주문) 의심 코드 — CLAUDE.md 안전규칙1: 사용자 명시 승인 필요:
$hits"

# 3) 비밀키·개인 데이터 커밋 금지
[ -n "$(git ls-files .env 2>/dev/null)" ] && violation ".env 이 git 에 추적됨 (안전규칙2)"
[ -n "$(git ls-files 'data_store/*' 2>/dev/null)" ] && violation "data_store/(개인 데이터)가 git 에 추적됨"

# 4) 백테스트 look-ahead 의심: 당일 신호로 당일 체결하는 패턴 (shift 제거 시 탐지)
if [ -f trading/backtest/engine.py ] && ! grep -q 'shift(1)' trading/backtest/engine.py; then
    violation "backtest/engine.py 에 t+1 체결(shift(1))이 없음 — look-ahead bias 의심"
fi

exit $fail
