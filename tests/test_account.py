"""가상계좌 직렬화·매매 규칙 회귀 테스트.

⚠️ from_dict 하위호환이 깨지면 VM에 쌓인 실계좌 데이터(data_store)를 못 읽는다.
"""
import unittest

from trading.paper.account import PaperAccount, Holding
from trading.paper.trader import in_cooldown


class TestSerialization(unittest.TestCase):
    def test_왕복_직렬화(self):
        a = PaperAccount()
        a.buy("A", 100.0, krw_amount=1_000, name="에이")
        a.cooldowns["B"] = "2026-07-03"
        b = PaperAccount.from_dict(a.to_dict())
        self.assertEqual(b.holdings["A"].shares, a.holdings["A"].shares)
        self.assertEqual(b.holdings["A"].peak_price, a.holdings["A"].peak_price)
        self.assertEqual(b.cooldowns, {"B": "2026-07-03"})
        self.assertAlmostEqual(b.cash, a.cash)

    def test_구버전_데이터_호환(self):
        """peak_price·cooldowns·buy_date 없던 이전 저장본도 읽혀야 한다(VM 데이터)."""
        old = {"cash": 5_000_000, "initial_capital": 10_000_000,
               "holdings": {"X": {"shares": 2, "avg_price": 100.0}}, "history": []}
        a = PaperAccount.from_dict(old)
        self.assertEqual(a.holdings["X"].shares, 2)
        self.assertEqual(a.holdings["X"].peak_price, 0.0)
        self.assertIsNone(a.holdings["X"].buy_date)   # 구데이터 → 최소보유 제한 없음
        self.assertEqual(a.cooldowns, {})

    def test_매수시_buy_date_기록(self):
        """최소 보유기간 판정 기준일 — 매수(추가매수 포함) 시각이 기록돼야 한다."""
        a = PaperAccount()
        a.buy("A", 100.0, krw_amount=10_000)
        self.assertIsNotNone(a.holdings["A"].buy_date)
        b = PaperAccount.from_dict(a.to_dict())      # 직렬화에도 보존
        self.assertEqual(b.holdings["A"].buy_date, a.holdings["A"].buy_date)


class TestTradingRules(unittest.TestCase):
    def test_배분액으로_1주도_못사면_매수안함(self):
        """비싼 종목이 배분 한도를 뚫지 못하게 — ETF 테마 도입 배경."""
        a = PaperAccount()
        rec = a.buy("EXPENSIVE", 3_000_000.0, krw_amount=2_000_000)
        self.assertIsNone(rec)
        self.assertNotIn("EXPENSIVE", a.holdings)
        self.assertEqual(a.cash, a.initial_capital)

    def test_매도시_보유제거_및_손익기록(self):
        a = PaperAccount()
        a.buy("A", 100.0, krw_amount=10_000)
        rec = a.sell("A", 110.0, reason="손절(-8%)")
        self.assertNotIn("A", a.holdings)
        self.assertEqual(rec["reason"], "손절(-8%)")
        self.assertIn("pnl", rec)

    def test_쿨다운_영업일_계산(self):
        # 2026-07-03(금) 손절 → 07-06(월)은 1영업일 경과 → 3일 쿨다운에 걸림
        self.assertTrue(in_cooldown("2026-07-03", "2026-07-06", days=3))
        # 07-09(목)는 4영업일 경과 → 재매수 허용
        self.assertFalse(in_cooldown("2026-07-03", "2026-07-09", days=3))
        self.assertFalse(in_cooldown(None, "2026-07-09", days=3))


if __name__ == "__main__":
    unittest.main()
