"""텔레그램 명령 응답 빌더·풋터 회귀 테스트 (네트워크 불필요한 것만)."""
import unittest

from trading.notify.telegram import HELP_FOOTER, append_help_footer
from trading.paper.account import PaperAccount
from watch import TG_HELP, cmd_config, cmd_plan, cmd_trades


class TestDisplayName(unittest.TestCase):
    def test_한글사전_우선(self):
        from trading.profile.themes import display_name
        self.assertEqual(display_name("NVDA"), "엔비디아")
        self.assertEqual(display_name("069500"), "KODEX 200")
        self.assertEqual(display_name("RBLX", "RBLX"), "로블록스")

    def test_사전에없으면_폴백순서(self):
        from trading.profile.themes import display_name
        self.assertEqual(display_name("XXXX", "어떤회사"), "어떤회사")   # FDR 이름
        self.assertEqual(display_name("XXXX", "XXXX"), "XXXX")          # 이름조회 실패
        self.assertEqual(display_name("XXXX"), "XXXX")                  # 코드 그대로

    def test_리포트_이름해석_통합(self):
        """미국 티커로 산 기록도 한글명으로 표시돼야 한다."""
        from trading.paper.analytics import name_of
        a = PaperAccount()
        a.buy("NVDA", 100.0, krw_amount=10_000, name="NVDA")   # FDR이 티커만 준 상황
        self.assertEqual(name_of(a, "NVDA"), "엔비디아")


class TestHelpFooter(unittest.TestCase):
    def test_모든_메시지에_풋터(self):
        out = append_help_footer("리포트 본문")
        self.assertTrue(out.endswith(HELP_FOOTER))

    def test_도움말에는_중복부착_안함(self):
        self.assertEqual(append_help_footer(TG_HELP), TG_HELP)


class TestCommandBuilders(unittest.TestCase):
    def make_account(self):
        a = PaperAccount()
        th = {"planned_at": "2026-07-18", "entry_price": 100.0,
              "expected_hold_bdays": 10, "expected_exit_date": "2026-08-01",
              "expected_return_pct": 5.0, "target_price": 105.0, "stop_price": 92.0}
        a.buy("PLAN", 100.0, krw_amount=10_000, name="계획주", thesis=th)
        a.buy("OLD", 100.0, krw_amount=10_000, name="구보유주")   # 계획서 없음
        a.holdings["OLD"].thesis = None
        a.sell("OLD", 90.0, reason="손절(-8%)")
        return a

    def test_config_핵심파라미터_노출(self):
        out = cmd_config()
        for kw in ("손절", "트레일링", "최소보유", "쿨다운", "현금버퍼"):
            self.assertIn(kw, out)

    def test_plan_디데이와_구보유_구분(self):
        a = self.make_account()
        out = cmd_plan(a, {"PLAN": 103.0})
        self.assertIn("회수예정 08-01", out)
        self.assertIn("+3.0%", out)          # 현재 수익률
        self.assertIn("기대 +5.0%", out)

    def test_plan_계획서없는_구보유_표기(self):
        a = PaperAccount()
        a.buy("OLD", 100.0, krw_amount=10_000)
        a.holdings["OLD"].thesis = None
        self.assertIn("계획서 없음", cmd_plan(a, {}))

    def test_trades_사유와_리뷰_노출(self):
        a = self.make_account()
        out = cmd_trades(a)
        self.assertIn("손절(-8%)", out)
        self.assertIn("🔴", out)
        self.assertIn("🟢", out)


if __name__ == "__main__":
    unittest.main()
