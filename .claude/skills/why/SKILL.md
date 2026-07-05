---
name: why
description: 특정 종목의 시그널·매매 이유 설명 — 추세/뉴스/선호 점수 분해와 매도점수(선호 제외), 최근 체결 사유까지. "왜 샀어/팔았어", "이 종목 분석 이유" 요청 시 사용. 인자로 종목코드 또는 이름.
---

# 시그널/매매 이유 설명 (/why <종목>)

## 절차
1. 종목코드 확인 (이름으로 오면 `trading/profile/themes.py` 나 웹에서 코드 찾기. 6자리 숫자=한국, 그 외=미국).
2. 점수 분해 실행 (실시간 데이터라 로컬 실행 OK):
```bash
./venv/bin/python - <<'EOF'
from trading.data import get_source
from trading.news import get_news_source
from trading.storage import get_storage
from trading.profile import UserProfile
from trading.signal import analyze_symbol
from trading.config import BUY_THRESHOLD, SELL_THRESHOLD

SYM = "여기에_종목코드"
profile = UserProfile.from_dict(get_storage('local').load_profile())
a = analyze_symbol(SYM, profile, get_source('fdr'), get_news_source('google'))
s = a.signal
print(f'{a.price.name}({SYM}) 종합 {s.total} → {s.action} (매수≥{BUY_THRESHOLD}/매도<{SELL_THRESHOLD})')
print(f'  추세 {s.trend} · 뉴스 {s.news} · 선호 {s.pref} · 가중치 {s.weights}')
print(f'  매도판정용(선호제외): {a.sell_signal.total} → {a.sell_signal.action}')
print('추세 근거:', *a.trend.reasons, sep='\n  · ')
print('뉴스 근거:', *a.news.reasons[:5], sep='\n  · ')
EOF
```
3. 실제 체결 이유를 물으면 VM 기록 조회:
```bash
ssh oracle-vm "cd stock-project && ./venv/bin/python -c \"
import json
d = json.load(open('data_store/_paper.json'))
for r in d['history']:
    if r['symbol'] == '종목코드': print(r['date'][:16], r['action'], r['shares'], '주 @', r['price'], r.get('reason',''))
\""
```

## 설명 시 명시할 것
- 매수는 종합점수(추세50%+뉴스30%+선호20%), **매도는 선호 제외 재가중**(추세62.5%+뉴스37.5%) — 왜 다른지: 선호가 하락 종목을 떠받치는 걸 막기 위함.
- 손절(-8%)·트레일링(-10%)은 점수와 무관한 강제 청산 (`trading/config.py`).
- 시그널은 참고용 — 투자 판단·책임은 사용자 본인.
