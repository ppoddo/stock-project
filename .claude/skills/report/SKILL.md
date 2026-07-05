---
name: report
description: 모의투자 현황 보고 — VM의 계좌·저널·최근 체결을 읽어 성과/보유/진단 요약. "상태 보고해", "요즘 어때", "얼마 벌었/잃었어" 류 요청 시 사용.
---

# 모의투자 현황 보고

## 원칙
- **읽기 전용.** 어떤 파일도 수정하지 않고, watch/dashboard 서비스를 재시작하지 않는다.
- **진짜 데이터는 VM에 있다.** 로컬 `data_store/`는 테스트 잔재 — 반드시 `ssh oracle-vm` 으로 조회.

## 절차
1. VM에서 현재가 반영 성과 조회 (아래 스니펫 그대로 사용):
```bash
ssh oracle-vm "cd stock-project && ./venv/bin/python - <<'EOF'
from trading.data import get_source
from trading.storage import get_storage
from trading.paper import PaperAccount, analyze_performance, load_equity_history
from trading.paper.trader import resolve_fx, to_krw

storage = get_storage('local'); src = get_source('fdr')
acct = PaperAccount.from_dict(storage.load_profile('_paper'))
fx = resolve_fx(src)
prices = {}
for s in acct.holdings:
    try:
        p = src.get_price(s, start='2026-01-01')
        prices[s] = to_krw(p.last_close, p.market, fx)
    except Exception as e:
        print('가격조회 실패:', s, e)
rep = analyze_performance(acct, prices, load_equity_history(storage))
print(f'총자산 {rep.total_value:,.0f}원 ({rep.total_return*100:+.2f}%) · 현금 {rep.cash:,.0f}원 · MDD {rep.mdd*100:.1f}% · 기록 {rep.days_tracked}일')
for p_ in rep.positions:
    print(f'  {p_.name}({p_.symbol}) {p_.shares}주 평단 {p_.avg_price:,.0f} 현재 {p_.cur_price:,.0f} 손익 {p_.pnl:,.0f}원 ({p_.pnl_pct*100:+.1f}%)')
print('진단:', *rep.reasons, sep='\n  · ')
for r in acct.history[-5:]:
    print('체결:', r['date'][:16], r['action'], r.get('name') or r['symbol'], r['shares'], '주', r.get('reason',''))
EOF"
```
2. 필요 시 `ssh oracle-vm "tail -20 stock-project/watch.log"` 로 워커 동작 확인.

## 보고 형식
- 결론 먼저: 총자산·수익률 한 줄.
- 종목별 손익 표 (매도 사유 reason 포함).
- 진단 reasons (섹터 집중·최대 손실 종목 등).
- 시사점 1~2개 (예: "현금 소진 — 매도 전까지 신규 매수 불가"). 투자 판단·책임은 사용자 본인임을 전제.
