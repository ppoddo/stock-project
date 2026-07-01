# 배포 가이드 — Oracle Cloud 무료 VM에 24시간 구동

목표: 내 컴퓨터를 꺼도 모의투자 워커(watch.py)가 클라우드에서 24시간 돌게 한다.
추천: **Oracle Cloud Always Free** (평생 무료). AWS Free Tier는 12개월 후 과금되어 비추천.

---

## 🅰️ 당신이 직접 (코드 밖 · 클라우드 콘솔)

### 1. Oracle Cloud 계정 만들기
- [ ] https://www.oracle.com/kr/cloud/free/ → "무료로 시작하기"
- [ ] 가입 (신용/체크카드 인증 필요 — **Always Free 리소스는 과금 안 됨**, 본인확인용)
- [ ] 홈 리전: **South Korea Central (Chuncheon)** 또는 가까운 곳 선택

### 2. VM 인스턴스 생성
- [ ] 콘솔 → Compute → Instances → **Create Instance**
- [ ] 이미지: **Canonical Ubuntu**(22.04 또는 24.04)
- [ ] Shape: **Always Free 표시** 있는 것
      - `VM.Standard.A1.Flex`(ARM, 넉넉) 또는 `VM.Standard.E2.1.Micro`(AMD 1GB)
      - ARM이 "용량 부족"이면 AMD Micro 선택 — 우리 봇엔 1GB로 충분
- [ ] **SSH 키**: "Generate a key pair" → **개인키(.key) 다운로드 후 보관** (재발급 불가)
- [ ] Create

### 3. 접속 준비
- [ ] 인스턴스의 **Public IP** 복사
- [ ] 내 PC 터미널에서 접속:
  ```bash
  chmod 400 ~/Downloads/받은키.key
  ssh -i ~/Downloads/받은키.key ubuntu@<Public-IP>
  ```

---

## 🅱️ 서버 안에서 (SSH 접속 후 · 명령 복붙)

### 4. 코드 세팅 (스크립트 한 방)
```bash
curl -sSL https://raw.githubusercontent.com/ppoddo/stock-project/main/deploy/setup.sh | bash
```
> 레포가 비공개면 위 curl 대신: `git clone` 시 GitHub 토큰이 필요해요. 그때 알려주면 방법 안내할게요.

### 5. 텔레그램 설정
```bash
cd ~/stock-project
nano .env
```
- [ ] `TELEGRAM_BOT_TOKEN=` 에 봇 토큰 입력
- [ ] `TELEGRAM_CHAT_ID=8757207694` 입력  (내 chat_id)
- [ ] Ctrl+O → Enter → Ctrl+X 로 저장

### 6. 한 번 테스트
```bash
./venv/bin/python watch.py --once
```
- [ ] 텔레그램으로 요약 오면 성공 ✅

### 7. systemd 로 24시간 등록 (재부팅·크래시 자동복구)
```bash
sudo cp ~/stock-project/deploy/watch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now watch.service
```
- [ ] 상태 확인: `systemctl status watch.service` → **active (running)**
- [ ] 로그 보기: `journalctl -u watch.service -f` 또는 `tail -f ~/stock-project/watch.log`

---

## ✅ 끝! 이제
- 내 PC를 꺼도 서버에서 **30분마다 자동운용 + 일일/주간 텔레그램 요약**
- 코드 업데이트 시:
  ```bash
  cd ~/stock-project && git pull && sudo systemctl restart watch.service
  ```

## 관리 명령 요약
| 하고 싶은 것 | 명령 |
|---|---|
| 상태 확인 | `systemctl status watch.service` |
| 로그 실시간 | `journalctl -u watch.service -f` |
| 재시작 | `sudo systemctl restart watch.service` |
| 정지 | `sudo systemctl stop watch.service` |
| 자동시작 끄기 | `sudo systemctl disable watch.service` |
