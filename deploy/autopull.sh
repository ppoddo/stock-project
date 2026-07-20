#!/usr/bin/env bash
# 자동 배포: origin/main 에 새 커밋이 있으면 pull → 검증 게이트(check.sh) → 서비스 재시작.
# 검증 실패 시 이전 커밋으로 즉시 롤백. 결과는 텔레그램으로 통지.
#
# 설치(VM, 1회):
#   sudo cp deploy/autopull.service deploy/autopull.timer /etc/systemd/system/
#   sudo systemctl daemon-reload && sudo systemctl enable --now autopull.timer
# 수동 실행: sudo systemctl start autopull.service (로그: /tmp/autopull-check.log)
set -u
cd "$(dirname "$0")/.." || exit 1

notify() {
    ./venv/bin/python - "$1" <<'PY' 2>/dev/null || true
import sys
from dotenv import load_dotenv
load_dotenv()
from trading.notify.telegram import TelegramNotifier
TelegramNotifier().send(sys.argv[1])
PY
}

git fetch -q origin main || exit 0
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)
[ "$LOCAL" = "$REMOTE" ] && exit 0          # 새 커밋 없음 — 조용히 종료

git pull --ff-only -q || exit 0
SUBJ=$(git log -1 --format=%s)

if bash scripts/check.sh > /tmp/autopull-check.log 2>&1; then
    sudo systemctl restart watch dashboard
    notify "🚀 <b>자동배포 완료</b> (${REMOTE:0:7})
${SUBJ}
검증 게이트 통과 · 워커/대시보드 재시작"
else
    git reset --hard -q "$LOCAL"            # 검증 실패 → 롤백, 기존 버전으로 계속 운용
    notify "⛔ <b>자동배포 실패 — 롤백됨</b> (${REMOTE:0:7})
${SUBJ}
scripts/check.sh 실패 → 이전 버전(${LOCAL:0:7})으로 계속 운용 중. VM의 /tmp/autopull-check.log 확인"
fi
