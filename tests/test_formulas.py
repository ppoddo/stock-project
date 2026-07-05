"""핵심 수식 회귀 테스트 — 시그널 가중합·매도 재가중·추세 점수 일관성.

⚠️ 이 테스트들은 '전략의 수학'을 지킨다. 깨지면 코드를 고치기 전에
   docs/tuning-result.md 와 CLAUDE.md 안전규칙4(숫자로 검증)를 먼저 읽을 것.
"""
import unittest

import numpy as np
import pandas as pd

from trading.analysis import trend_score
from trading.analysis.trend import trend_score_series
from trading.config import BUY_THRESHOLD, SELL_THRESHOLD
from trading.signal.engine import (
    DEFAULT_WEIGHTS, combine_scores, decide_action, reweight_without_pref, sell_score,
)


class TestSignalFormula(unittest.TestCase):
    def test_가중합이_정의대로(self):
        r = combine_scores(trend=60, news=40, pref=80)
        expect = 60 * 0.5 + 40 * 0.3 + 80 * 0.2
        self.assertAlmostEqual(r.total, round(expect, 1))

    def test_임계값은_config_단일출처(self):
        self.assertEqual(decide_action(BUY_THRESHOLD), "매수")
        self.assertEqual(decide_action(SELL_THRESHOLD), "관망")   # 경계는 관망(미만만 매도)
        self.assertEqual(decide_action(SELL_THRESHOLD - 0.1), "매도")

    def test_매도재가중_합이_1이고_선호는_0(self):
        w = reweight_without_pref(DEFAULT_WEIGHTS)
        self.assertAlmostEqual(sum(w.values()), 1.0)
        self.assertEqual(w["pref"], 0.0)
        self.assertAlmostEqual(w["trend"], 0.5 / 0.8)

    def test_하락종목을_선호가_못_떠받침(self):
        """추세 폭락 + 선호 높음 → 매수점수는 버텨도 매도점수는 매도로 떨어져야 한다."""
        buy_side = combine_scores(trend=25, news=40, pref=90)
        sell_side = sell_score(trend=25, news=40)
        self.assertLess(sell_side.total, buy_side.total)
        self.assertEqual(sell_side.action, "매도")

    def test_재가중_분모0_폴백(self):
        w = reweight_without_pref({"trend": 0.0, "news": 0.0, "pref": 1.0})
        self.assertEqual(w, {"trend": 1.0, "news": 0.0, "pref": 0.0})


class TestTrendConsistency(unittest.TestCase):
    def test_단건과_시계열_공식이_일치(self):
        """trend_score(마지막날) == trend_score_series 마지막 값 — 두 구현이 같은 수식이어야
        백테스트(시계열)로 튜닝한 값을 실운용(단건)에 적용할 수 있다."""
        rng = np.random.default_rng(42)
        rets = rng.normal(0.0005, 0.02, 250)
        close = 100 * np.cumprod(1 + rets)
        df = pd.DataFrame({"Close": close},
                          index=pd.date_range("2025-01-01", periods=250, freq="B"))
        single = trend_score(df).score
        series = trend_score_series(df).iloc[-1]
        self.assertAlmostEqual(single, series, delta=0.11)  # 각각 0.1 반올림 허용


if __name__ == "__main__":
    unittest.main()
