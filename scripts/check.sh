#!/usr/bin/env bash
# 커밋 전 검증 게이트 — 사람/AI 공용. 전부 통과하지 않으면 커밋·배포 금지.
# 사용: bash scripts/check.sh
set -eo pipefail
cd "$(dirname "$0")/.."
PY=./venv/bin/python

echo "── 1) 가드(안전규칙 정적 검사) ──"
bash scripts/guard.sh
echo "통과"

echo "── 2) 문법 컴파일 ──"
git ls-files '*.py' | xargs "$PY" -m py_compile
echo "통과"

echo "── 3) 단위 테스트(핵심 수식 회귀) ──"
"$PY" -m unittest discover -s tests -t . -q

echo ""
echo "✅ 모든 검사 통과 — 커밋해도 됩니다"
