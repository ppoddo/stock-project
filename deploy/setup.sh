#!/usr/bin/env bash
# VM 초기 세팅 — Oracle/AWS Ubuntu 인스턴스에서 1회 실행
# 사용법:  bash setup.sh
set -euo pipefail

REPO="https://github.com/ppoddo/stock-project.git"
DIR="$HOME/stock-project"

echo "==> 패키지 설치 (Python 3.12, git)"
# Ubuntu 22.04 기본 python3.10 은 최신 pandas(>=3.11 요구) 불가 → deadsnakes 로 3.12 설치
sudo apt-get update -y
sudo apt-get install -y software-properties-common git
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt-get update -y
sudo apt-get install -y python3.12 python3.12-venv

# 이후 단계에서 쓸 파이썬 실행기 (3.12 우선, 없으면 python3)
PY=$(command -v python3.12 || command -v python3)
echo "    사용 파이썬: $PY ($($PY --version))"

echo "==> 레포 클론/업데이트"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" pull
else
  git clone "$REPO" "$DIR"
fi
cd "$DIR"

echo "==> 가상환경 + 의존성"
rm -rf venv                      # 이전 실패한 venv 정리 후 재생성
"$PY" -m venv venv
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
