"""매매 계획서(thesis) 회귀 테스트 — 평가·회수예측·리뷰 채점·직렬화.

⚠️ 계획서는 알고리즘 자체 평가(/retro)의 원천 데이터 — 스키마가 조용히 바뀌면
   과거 기록과 비교가 불가능해진다. 필드 변경 시 하위호환을 지킬 것.
"""
import unittest

import numpy as np
import pandas as pd

from trading.paper.account import PaperAccount
from trading.paper.thesis import build_thesis, review_exit


def uptrend_df(n=200):
    """추세 거래가 몇 번 나오도록 등락이 있는 합성 시계열."""
    rng = np.random.default_rng(7)
    rets = rng.normal(0.001, 0.02, n)
    close = 100 * np.cumprod(1 + rets)
    return pd.DataFrame({"Close": close},
                        index=pd.date_range("2025-01-01", periods=n, freq="B"))


class TestBuildThesis(unittest.TestCase):
    def test_계획서_필수필드와_회수예측(self):
        th = build_thesis(uptrend_df(), price_krw=50_000,
                          scores={"trend": 70, "news": 55, "pref": 90, "total": 71.5},
                          today_iso="2026-07-08")
        for key in ("planned_at", "entry_price", "scores", "expected_hold_bdays",
                    "expected_exit_date", "expected_return_pct", "target_price",
                    "stop_price", "bt_win_rate"):
            self.assertIn(key, th)
        self.assertGreaterEqual(th["expected_hold_bdays"], 1)
        self.assertGreater(th["expected_exit_date"], th["planned_at"])  # 회수일은 미래
        self.assertLess(th["stop_price"], 50_000)                       # 손절선은 매수가 아래
        import json
        json.dumps(th)  # JSON 직렬화 가능해야 함 (계좌 저장 포맷)


class TestReviewExit(unittest.TestCase):
    TH = {"planned_at": "2026-07-01", "entry_price": 100.0,
          "expected_hold_bdays": 10, "expected_return_pct": 5.0}

    def test_조기회수_판정(self):
        rv = review_exit(self.TH, sell_price=98.0, sell_reason="시그널(선호제외)",
                         today_iso="2026-07-03")   # 2영업일 < 예상 10일의 절반
        self.assertEqual(rv["timing"], "조기회수")
        self.assertFalse(rv["return_hit"])          # -2% < 기대 +5%

    def test_계획범위_및_기대달성(self):
        rv = review_exit(self.TH, sell_price=106.0, sell_reason="시그널(선호제외)",
                         today_iso="2026-07-14")   # 9영업일 ≈ 예상 10일
        self.assertEqual(rv["timing"], "계획범위")
        self.assertTrue(rv["return_hit"])           # +6% ≥ 기대 +5%

    def test_계획서없는_구데이터는_None(self):
        self.assertIsNone(review_exit(None, 100.0, "손절(-8%)"))


class TestAccountIntegration(unittest.TestCase):
    def test_매수시_계획서저장_매도시_리뷰기록(self):
        a = PaperAccount()
        th = {"planned_at": "2026-07-01", "entry_price": 100.0,
              "expected_hold_bdays": 10, "expected_return_pct": 5.0}
        a.buy("A", 100.0, krw_amount=10_000, thesis=th)
        self.assertEqual(a.holdings["A"].thesis, th)
        # 직렬화 왕복에도 계획서 보존
        b = PaperAccount.from_dict(a.to_dict())
        self.assertEqual(b.holdings["A"].thesis, th)
        # 매도 시 리뷰가 기록에 남는다
        rec = b.sell("A", 110.0, reason="시그널(선호제외)")
        self.assertIn("review", rec)
        self.assertIn(rec["review"]["timing"], ("조기회수", "계획범위", "지연회수"))

    def test_계획서없는_매도도_정상(self):
        a = PaperAccount()
        a.buy("B", 100.0, krw_amount=10_000)   # thesis 미전달 (구 방식)
        rec = a.sell("B", 90.0, reason="손절(-8%)")
        self.assertIsNotNone(rec)
        self.assertNotIn("review", rec)


if __name__ == "__main__":
    unittest.main()
