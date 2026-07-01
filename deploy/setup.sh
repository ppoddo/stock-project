#!/usr/bin/env bash
# VM 초기 세팅 — Oracle/AWS Ubuntu 인스턴스에서 1회 실행
# 사용법:  bash setup.sh
set -euo pipefail

REPO="https://github.com/ppoddo/stock-project.git"
DIR="$HOME/stock-project"

echo "==> 패키지 설치 (python venv, git)"
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git

echo "==> 레포 클론/업데이트"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

echo "==> 가상환경 + 의존성"
python3 -m venv venv
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q

echo "==> .env 준비"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "‼️  .env 를 열어 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 를 입력하세요:"
  echo "     nano $DIR/.env"
fi

echo ""
echo "✅ 세팅 완료. 다음 순서:"
echo "  1) nano .env   (텔레그램 토큰/chat_id 입력)"
echo "  2) 테스트:  ./venv/bin/python watch.py --once"
echo "  3) 상시구동: DEPLOY.md 의 systemd 등록 단계 진행"
