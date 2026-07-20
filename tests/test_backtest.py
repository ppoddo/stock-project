"""백테스트 엔진 회귀 테스트 — look-ahead 금지 · 손절 동작.

⚠️ 't일 신호 → t+1일 체결'은 이 프로젝트의 생명선이다.
   이 테스트가 깨지는 수정은 성과를 허위로 부풀린다 — 절대 우회하지 말 것.
"""
import unittest

import pandas as pd

from trading.backtest import run_backtest


def make_df(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    return pd.DataFrame({"Close": [float(c) for c in closes]}, index=idx)


def scores(vals: list[float], df: pd.DataFrame) -> pd.Series:
    return pd.Series([float(v) for v in vals], index=df.index)


class TestLookAhead(unittest.TestCase):
    def test_신호일_당일수익은_먹지_못한다(self):
        """급등이 '신호가 뜬 날' 발생 → t+1 체결이므로 그 수익은 못 먹어야 정상."""
        df = make_df([100, 100, 110, 110, 110])   # 급등은 idx2
        s = scores([50, 50, 70, 50, 50], df)      # 매수신호도 idx2 (당일)
        r = run_backtest(df, score_series=s, buy_th=60, sell_th=40, fee=0.0)
        self.assertAlmostEqual(r.total_return, 0.0, places=6)

    def test_신호_다음날_수익은_먹는다(self):
        df = make_df([100, 100, 100, 110, 110])   # 급등은 idx3
        s = scores([50, 50, 70, 50, 50], df)      # 매수신호는 idx2 (전날)
        r = run_backtest(df, score_series=s, buy_th=60, sell_th=40, fee=0.0)
        self.assertAlmostEqual(r.total_return, 0.10, places=6)


class TestStopLoss(unittest.TestCase):
    def test_손절이_추가하락을_차단(self):
        """진입가 대비 -8% 이탈(t일 종가) → t+1일 청산 → 이후 반등을 안 먹더라도
        추가 하락에서 보호. 손절 없는 실행과 자산곡선이 달라야 한다."""
        closes = [100, 100, 100, 95, 91, 91, 60, 60, 60, 60]  # idx4에서 -9%, 이후 폭락
        df = make_df(closes)
        s = scores([70] * len(closes), df)        # 시그널은 계속 '보유'를 원함
        no_stop = run_backtest(df, score_series=s, buy_th=60, sell_th=40, fee=0.0)
        with_stop = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                                 fee=0.0, stop_loss=0.08)
        self.assertLess(no_stop.total_return, with_stop.total_return)
        # 손절 시점(-9% 판정 다음날)까지의 손실만 반영: 91/100 - 1 = -9%
        self.assertAlmostEqual(with_stop.total_return, -0.09, places=6)

    def test_손절도_lookahead_없음(self):
        """손절 판정일(t) 종가 하락분은 그대로 맞고, t+1부터 현금이어야 한다."""
        closes = [100, 100, 90, 50, 50]           # idx2에서 -10% 판정, idx3 폭락
        df = make_df(closes)
        s = scores([70] * 5, df)
        r = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                         fee=0.0, stop_loss=0.08)
        # idx2의 -10%는 맞음(판정 당일), idx3의 -44%는 회피(청산 후)
        self.assertAlmostEqual(r.total_return, -0.10, places=6)


class TestMinHold(unittest.TestCase):
    def test_최소보유기간내_시그널청산_보류(self):
        """진입 직후 매도신호가 떠도 min_hold_days 동안은 보유 유지(왕복 방지)."""
        closes = [100, 100, 100, 110, 120, 120]
        df = make_df(closes)
        s = scores([70, 30, 30, 30, 30, 30], df)   # idx0 매수 → idx1부터 즉시 매도신호
        no_hold = run_backtest(df, score_series=s, buy_th=60, sell_th=40, fee=0.0)
        held = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                            fee=0.0, min_hold_days=3)
        # 보유연장 없으면 idx1 진입→idx2 청산(수익 0), 3일 보유 시 idx3 +10% 흡수
        self.assertAlmostEqual(no_hold.total_return, 0.0, places=6)
        self.assertGreater(held.total_return, 0.09)

    def test_최소보유중에도_손절은_동작(self):
        """최소 보유기간은 시그널 매도만 보류 — 손절은 리스크 차단이라 예외 없다."""
        closes = [100, 100, 90, 50, 50, 50]
        df = make_df(closes)
        s = scores([70] * 6, df)
        r = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                         fee=0.0, stop_loss=0.08, min_hold_days=5)
        self.assertAlmostEqual(r.total_return, -0.10, places=6)  # 손절 없인 -50%


class TestTrailingStop(unittest.TestCase):
    def test_고점대비_이탈시_다음날_청산(self):
        """+20% 상승 후 고점 대비 -10% → t+1일 청산. 이후 폭락 회피."""
        closes = [100, 100, 120, 107, 40, 40]   # idx3: 120→107 = 고점대비 -10.8%
        df = make_df(closes)
        s = scores([70] * 6, df)
        r = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                         fee=0.0, trailing_stop=0.10)
        # idx1 진입(100) → idx2 +20% → idx3 -10.8%(판정, 당일 하락은 맞음) → idx4부터 현금
        self.assertAlmostEqual(r.total_return, 0.07, places=6)   # 107/100 - 1

    def test_arm_설정시_수익권_전엔_트레일링_비활성(self):
        """진입 직후 고점≈진입가 상태에서 트레일링이 손절 역할을 하면 안 된다(arm)."""
        closes = [100, 100, 103, 92, 92, 92]    # 고점 103(+3%) → 92 = 고점대비 -10.7%
        df = make_df(closes)
        s = scores([70] * 6, df)
        armed_always = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                                    fee=0.0, trailing_stop=0.10)
        armed_5pct = run_backtest(df, score_series=s, buy_th=60, sell_th=40,
                                  fee=0.0, trailing_stop=0.10, trailing_arm=0.05)
        # 항상 활성(현행 라이브): idx3 청산 → -8% 확정. arm 5%: 고점 +3%뿐 → 미발동, 계속 보유
        self.assertAlmostEqual(armed_always.total_return, -0.08, places=6)
        self.assertAlmostEqual(armed_5pct.total_return, -0.08, places=6)  # 평가손 동일하나
        # 차이는 '청산 여부' — 항상활성은 현금(이후 회복 못 먹음), arm은 보유 유지
        closes2 = closes + [110]
        df2 = make_df(closes2)
        s2 = scores([70] * 7, df2)
        always2 = run_backtest(df2, score_series=s2, buy_th=60, sell_th=40,
                               fee=0.0, trailing_stop=0.10)
        arm2 = run_backtest(df2, score_series=s2, buy_th=60, sell_th=40,
                            fee=0.0, trailing_stop=0.10, trailing_arm=0.05)
        self.assertAlmostEqual(always2.total_return, -0.08, places=6)  # 반등 놓침
        self.assertAlmostEqual(arm2.total_return, 0.10, places=6)      # 보유 유지 → 회복


class TestDefaults(unittest.TestCase):
    def test_기본_임계값은_config에서(self):
        from trading.config import BT_BUY_TH, BT_SELL_TH
        df = make_df([100] * 130)
        r = run_backtest(df)
        self.assertEqual(r.buy_th, BT_BUY_TH)
        self.assertEqual(r.sell_th, BT_SELL_TH)


if __name__ == "__main__":
    unittest.main()
