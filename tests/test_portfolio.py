"""포트폴리오 캡·랭킹 매수 회귀 테스트 (2026-07-08 "카테고리 몰빵" 처방).

execute_buys 는 네트워크 없이 actions/prices 만으로 동작한다 — 여기서 규칙을 박제한다.
"""
import unittest

from trading.config import CASH_BUFFER_PCT, MAX_POSITIONS
from trading.paper.account import PaperAccount
from trading.paper.trader import blocked_by_theme_cap, execute_buys


def cand(total: float) -> dict:
    """매수 후보 actions 항목 (df=None → thesis 생략 경로)."""
    return {"buy": "매수", "sell": "관망", "name": "",
            "scores": {"trend": 60, "news": 50, "pref": 80, "total": total},
            "df": None}


class TestRanking(unittest.TestCase):
    def test_점수높은순으로_현금을_쓴다(self):
        """현금이 2종목치뿐이면 점수 1·2위만 사야 한다 (스캔 순서 무관).

        dict 순서는 LOW 가 먼저 — 랭킹이 없다면 LOW 부터 사게 된다.
        """
        a = PaperAccount(cash=3_000_000, initial_capital=10_000_000)
        # 버퍼 100만 제외 가용 200만 · 1주 90만 → 2종목 사면 3위 몫이 없다
        actions = {"LOW": cand(66), "TOP": cand(90), "MID": cand(75)}
        prices = {"LOW": 900_000, "TOP": 900_000, "MID": 900_000}
        execute_buys(a, actions, prices, "2026-07-08", pos_pct=0.10)
        self.assertIn("TOP", a.holdings)
        self.assertIn("MID", a.holdings)
        self.assertNotIn("LOW", a.holdings)   # 3위는 현금버퍼에 막힘
        self.assertGreaterEqual(a.cash, 1_000_000)  # 버퍼 보존


class TestCaps(unittest.TestCase):
    def test_최대보유종목수_상한(self):
        a = PaperAccount(cash=100_000_000, initial_capital=100_000_000)
        actions = {f"S{i}": cand(90 - i) for i in range(MAX_POSITIONS + 5)}
        prices = {s: 10_000 for s in actions}
        execute_buys(a, actions, prices, "2026-07-08", pos_pct=0.01)
        self.assertEqual(len(a.holdings), MAX_POSITIONS)

    def test_테마캡_같은테마_몰빵차단(self):
        """반도체 2종목 보유 중이면 세 번째 반도체(NVDA)는 사지 않는다."""
        a = PaperAccount(cash=50_000_000, initial_capital=50_000_000)
        a.holdings["005930"] = a.holdings.get("005930") or __import__(
            "trading.paper.account", fromlist=["Holding"]).Holding(shares=1, avg_price=1)
        a.holdings["000660"] = __import__(
            "trading.paper.account", fromlist=["Holding"]).Holding(shares=1, avg_price=1)
        self.assertTrue(blocked_by_theme_cap("NVDA", a.holdings, cap=2))
        self.assertFalse(blocked_by_theme_cap("035720", a.holdings, cap=2))  # 카카오는 다른 테마
        actions = {"NVDA": cand(95), "035720": cand(70)}
        prices = {"NVDA": 100_000, "035720": 50_000}
        execute_buys(a, actions, prices, "2026-07-08", pos_pct=0.02)
        self.assertNotIn("NVDA", a.holdings)   # 점수 1위여도 테마캡에 차단
        self.assertIn("035720", a.holdings)

    def test_현금버퍼는_침범하지_않는다(self):
        a = PaperAccount(cash=1_500_000, initial_capital=10_000_000)
        actions = {"X": cand(90)}
        prices = {"X": 100_000}
        execute_buys(a, actions, prices, "2026-07-08", pos_pct=0.20)
        # 버퍼 100만 → 가용 50만 → 4주(40만+수수료)까지만. 현금은 버퍼 이상 유지
        self.assertGreaterEqual(a.cash, 10_000_000 * CASH_BUFFER_PCT)
        self.assertEqual(a.holdings["X"].shares, 4)

    def test_쿨다운중이면_후보제외(self):
        a = PaperAccount(cash=10_000_000, initial_capital=10_000_000)
        a.cooldowns["X"] = "2026-07-07"   # 어제 매도 → 3영업일 쿨다운
        actions = {"X": cand(95)}
        prices = {"X": 10_000}
        execute_buys(a, actions, prices, "2026-07-08")
        self.assertNotIn("X", a.holdings)


if __name__ == "__main__":
    unittest.main()
