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


class TestDefaults(unittest.TestCase):
    def test_기본_임계값은_config에서(self):
        from trading.config import BT_BUY_TH, BT_SELL_TH
        df = make_df([100] * 130)
        r = run_backtest(df)
        self.assertEqual(r.buy_th, BT_BUY_TH)
        self.assertEqual(r.sell_th, BT_SELL_TH)


if __name__ == "__main__":
    unittest.main()
