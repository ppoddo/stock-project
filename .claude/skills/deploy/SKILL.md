---
name: deploy
description: 검증 게이트 → 커밋/푸시 → Oracle VM 반영 → 가동 확인까지의 배포 절차. "배포해줘", "VM에 반영해" 요청 시 사용.
---

# 배포 (/deploy)

## 절차 — 순서 엄수
1. **검증 게이트** (실패하면 여기서 중단하고 원인 보고):
```bash
bash scripts/check.sh
```
2. **커밋·푸시** — 관련 파일만 `git add`(경로 명시, `git add -A` 금지 — data_store/.env 방지는 gitignore가 하지만 습관화), 한국어 커밋 메시지:
```bash
git add <변경파일들> && git commit -m "..." && git push origin main
```
3. **VM 반영**:
```bash
ssh oracle-vm "cd stock-project && git pull --ff-only && sudo systemctl restart watch"
```
   - 문서/스킬/테스트만 바뀐 경우 restart 생략 가능 (pull만).
   - 대시보드(app.py) 변경 시: `sudo systemctl restart dashboard` 도 실행.
4. **가동 확인** (필수 — 이걸 봐야 배포 완료):
```bash
ssh oracle-vm "sudo systemctl is-active watch && tail -5 stock-project/watch.log"
```
   - `active` + 로그에 `모의투자 자동운용 시작` / `텔레그램 명령 대기` 가 보여야 정상.
   - 40종목 첫 사이클은 2~4분 걸림 — 로그가 바로 안 늘어도 기다릴 것.

## 환경 지식 (헤매지 말 것)
- SSH: `ssh oracle-vm` (~/.ssh/config 별칭, IP 161.33.34.189, 키 ~/oracle.key). 8501 포트포워딩이 겹치면 `bind: Address already in use` 경고가 뜨는데 **무해** — 무시.
- 로그: `journalctl` 아님! `~/stock-project/watch.log` 파일 (`StandardOutput=append`).
- 서비스 2개: `watch`(워커) · `dashboard`(스트림릿, 127.0.0.1 전용 — 외부 공개 금지).
- 텔레그램 getUpdates 폴링은 봇당 1곳 — **로컬에서 watch.py 실행 금지** (VM과 409 충돌).
- VM의 `data_store/` 는 실계좌 데이터 — 절대 덮어쓰거나 커밋하지 않는다.
