# AI 트레이딩 어시스턴트

시장 트렌드 · 뉴스 호재 · 선호 카테고리를 종합해 **주식/ETF 매수·매도 시그널**을 산출하고,
백테스팅 + 모의투자로 검증하는 개인용 트레이딩 어시스턴트. 한국(KRX) + 미국 시장 지원.

> ⚠️ **실거래 아님.** 모든 시그널은 참고용이며 투자 판단·책임은 본인에게 있습니다.

---

## 🗺️ 어디서 뭘 관리하나 (한눈에)

| 무엇 | 어디서 | 용도 |
|------|--------|------|
| 📦 **코드·이력** | [GitHub 레포](https://github.com/ppoddo/stock-project) | 소스코드, 변경 이력, 이 문서 |
| ☁️ **24시간 봇** | Oracle Cloud VM | 30분마다 모의투자 자동운용 (컴퓨터 꺼도 구동) |
| 📱 **알림·리포트** | 텔레그램 봇 대화방 | 일일/주간 모의투자 요약 받기 |
| 📊 **대시보드** | 내 PC (로컬 실행) | 종목 분석·백테스트·모의투자 현황 보기 |
| 📈 **누적 데이터** | 서버 `data_store/` | 자산 시계열(향후 그래프 분석용) |

---

## ☁️ 서버 관리 (Oracle VM · 24시간 봇)

SSH 접속 후 (`ssh -i <키> ubuntu@<서버IP>`):

| 하고 싶은 것 | 명령 |
|---|---|
| 잘 도는지 확인 | `systemctl status watch.service` |
| 실시간 로그 | `journalctl -u watch.service -f` |
| 재시작 | `sudo systemctl restart watch.service` |
| 정지 / 시작 | `sudo systemctl stop\|start watch.service` |
| 코드 업데이트 반영 | `cd ~/stock-project && git pull && sudo systemctl restart watch.service` |

> 배포 방법 전체는 [DEPLOY.md](DEPLOY.md) 참고.

## 📊 대시보드 (내 PC에서 볼 때만 실행)

```bash
./venv/bin/streamlit run app.py    # localhost:8501
```
탭 2개: **종목 분석**(트렌드·뉴스·시그널·백테스트) / **모의투자**(계좌·수익률·자산추이).

## 📱 텔레그램
봇 대화방으로 **일일/주간 요약**이 자동으로 와요. (실시간 매수/매도 알림 대신 정기 리포트)

---

## 🧭 다음 할 일
현재 진행 상황과 다음 단계는 [TODO.md](TODO.md) · [PLAN.md](PLAN.md) 참고.
- 모의투자 성과를 며칠 지켜보고 전략/가중치 검증
- (먼 미래, 명시 승인 시) 실거래 전환 — 그땐 **레포를 비공개로** 되돌릴 것

## 📂 구조
프로젝트 구조·아키텍처·안전 규칙은 [CLAUDE.md](CLAUDE.md)에 정리되어 있습니다.
