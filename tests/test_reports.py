"""리포트 슬롯(한국시 09/12/15/18/21)·성과분석 회귀 테스트."""
import unittest
from datetime import datetime

import watch
from watch import KST, maybe_send_summary
from trading.paper import PaperAccount
from trading.paper.analytics import analyze_performance


class FakeStore:
    def __init__(self):
        self.d = {}

    def load_profile(self, key="_p"):
        return dict(self.d.get(key, {}))

    def save_profile(self, data, key="_p"):
        self.d[key] = data


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, m):
        self.sent.append(m)
        return True


def t(hour, minute=0, day=7):  # 2026-07-07(화) 기본 — 주중, 주 중간
    return datetime(2026, 7, day, hour, minute, tzinfo=KST)


class TestReportSlots(unittest.TestCase):
    def setUp(self):
        self._orig = (watch.load_equity_history, watch.build_summary)
        watch.load_equity_history = lambda s: []
        watch.build_summary = lambda *a, **k: "리포트"
        self.store, self.noti, self.acct = FakeStore(), FakeNotifier(), PaperAccount()
        # 주간 리포트는 슬롯 로직과 무관하므로 발송된 상태로 시작
        self.store.d["_report_state"] = {"last_weekly": "2026-W28"}

    def tearDown(self):
        watch.load_equity_history, watch.build_summary = self._orig

    def send(self, now, force=False):
        return maybe_send_summary(self.acct, {}, self.noti, self.store,
                                  force_daily=force, now=now)

    def test_슬롯전에는_발송없음(self):
        self.assertEqual(self.send(t(8, 30)), [])

    def test_정각발송_그리고_중복방지(self):
        self.assertEqual(self.send(t(9, 0)), ["09시"])
        self.assertEqual(self.send(t(9, 20)), [])
        self.assertEqual(self.send(t(11, 59)), [])
        self.assertEqual(self.send(t(12, 1)), ["12시"])

    def test_재시작_캐치업은_최근슬롯_1회만(self):
        self.assertEqual(self.send(t(22, 30)), ["21시"])   # 15·18시는 건너뛰고 최신만
        self.assertEqual(self.send(t(23, 0)), [])

    def test_수동요청은_슬롯무관(self):
        self.assertEqual(self.send(t(7, 0), force=True), ["수동"])


class TestAnalytics(unittest.TestCase):
    def test_데이터_1행이어도_안죽음(self):
        r = analyze_performance(PaperAccount(), {}, [{"date": "2026-06-20", "total": 1.0}])
        self.assertFalse(r.data_sufficient)
        self.assertEqual(r.mdd, 0.0)
        self.assertTrue(any("쌓이면" in s for s in r.reasons))  # 데이터 부족 안내 문구

    def test_저널없어도_안죽음(self):
        r = analyze_performance(PaperAccount(), {}, None)
        self.assertFalse(r.data_sufficient)


if __name__ == "__main__":
    unittest.main()
