"""모의투자 가상계좌 (요구사항 — 펀드매니저식 자동운용).

실제 돈이 아닌 가상 현금으로 매수/매도를 기록하고 수익률을 추적한다.
⚠️ 실거래 아님. 안전규칙1: 실제 주문 코드는 명시적 승인 전까지 없음.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..config import FEE  # 거래비용(왕복 근사) — 단일 출처(config)
from .thesis import review_exit

DEFAULT_CAPITAL = 10_000_000  # 초기 가상자본 (원)


@dataclass
class Holding:
    """보유 종목."""

    shares: int
    avg_price: float          # 평균 매입가
    peak_price: float = 0.0   # 보유 중 고점(트레일링 스탑용) — WP2. 미저장 구데이터는 0.0
    buy_date: str | None = None  # 마지막 매수 시각 ISO — 최소보유기간 판정용. 구데이터는 None(제한 없음)
    thesis: dict | None = None   # 매매 계획서(평가·회수예측) — thesis.build_thesis(). 구데이터는 None

    def to_dict(self) -> dict:
        return {"shares": self.shares, "avg_price": self.avg_price,
                "peak_price": self.peak_price, "buy_date": self.buy_date,
                "thesis": self.thesis}


@dataclass
class PaperAccount:
    """가상 계좌: 현금 + 보유종목 + 거래기록."""

    cash: float = DEFAULT_CAPITAL
    initial_capital: float = DEFAULT_CAPITAL
    holdings: dict[str, Holding] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)
    cooldowns: dict[str, str] = field(default_factory=dict)  # symbol -> 마지막 손절일 ISO date (WP2 재진입 쿨다운)

    # ── 매매 ──────────────────────────────────────────
    def buy(self, symbol: str, price: float, krw_amount: float, name: str = "",
            thesis: dict | None = None) -> dict | None:
        """krw_amount(원화) 예산 안에서 최대 정수주 매수(수수료 포함).

        예산은 현금 한도를 넘지 않으며, 1주도 못 사면 매수하지 않는다(None).
        → 종목당 배분 한도를 항상 지킨다(비싼 1주로 한도를 넘기지 않음).
        """
        unit_cost = price * (1 + FEE)
        budget = min(krw_amount, self.cash)
        shares = int(budget // unit_cost)
        if shares <= 0:
            return None
        cost = shares * unit_cost
        self.cash -= cost
        h = self.holdings.get(symbol)
        if h:  # 추가 매수 → 평균단가 갱신
            total = h.shares + shares
            h.avg_price = (h.avg_price * h.shares + price * shares) / total
            h.shares = total
        else:
            self.holdings[symbol] = Holding(shares=shares, avg_price=price)
        # 트레일링 스탑용 고점 초기화/갱신 (WP2) + 최소보유기간 기준일 + 매매 계획서
        h = self.holdings[symbol]
        h.peak_price = max(h.peak_price or 0.0, price)
        h.buy_date = datetime.now().isoformat(timespec="seconds")
        if thesis is not None:
            h.thesis = thesis
        return self._record(symbol, name, "매수", shares, price, cost)

    def sell(self, symbol: str, price: float, name: str = "",
             reason: str = "시그널") -> dict | None:
        """보유 전량 매도. 체결 내역 dict 반환(미보유 시 None).

        reason: 매도 사유(시그널/손절/트레일링 등) — 리포트·저널에 노출(WP2).
        """
        h = self.holdings.get(symbol)
        if not h or h.shares <= 0:
            return None
        proceeds = h.shares * price * (1 - FEE)
        pnl = proceeds - h.shares * h.avg_price
        self.cash += proceeds
        review = review_exit(h.thesis, price, reason)  # 계획 대비 실제 자동 채점(계획서 없으면 None)
        rec = self._record(symbol, name, "매도", h.shares, price, proceeds,
                           pnl=pnl, reason=reason, review=review)
        del self.holdings[symbol]
        return rec

    def _record(self, symbol, name, action, shares, price, amount,
                pnl=None, reason=None, review=None) -> dict:
        rec = {
            "date": datetime.now().isoformat(timespec="seconds"),
            "symbol": symbol, "name": name, "action": action,
            "shares": shares, "price": round(price, 2), "amount": round(amount, 0),
        }
        if pnl is not None:
            rec["pnl"] = round(pnl, 0)
        if reason is not None:
            rec["reason"] = reason
        if review is not None:
            rec["review"] = review  # 매매 계획 대비 실제 (조기/계획범위/지연 · 기대수익 달성 여부)
        self.history.append(rec)
        return rec

    # ── 평가 ──────────────────────────────────────────
    def market_value(self, prices: dict[str, float]) -> float:
        """보유종목 평가액(현재가 기준). 가격 없으면 평균단가로 대체."""
        total = 0.0
        for sym, h in self.holdings.items():
            px = prices.get(sym, h.avg_price)
            total += h.shares * px
        return total

    def total_value(self, prices: dict[str, float]) -> float:
        """총자산 = 현금 + 보유평가액."""
        return self.cash + self.market_value(prices)

    def total_return(self, prices: dict[str, float]) -> float:
        """초기자본 대비 총수익률."""
        return self.total_value(prices) / self.initial_capital - 1

    def position_pnl(self, symbol: str, price: float) -> tuple[float, float]:
        """종목 평가손익(금액, 수익률)."""
        h = self.holdings[symbol]
        cost = h.shares * h.avg_price
        value = h.shares * price
        return value - cost, (value / cost - 1) if cost else 0.0

    # ── 저장 ──────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "cash": self.cash,
            "initial_capital": self.initial_capital,
            "holdings": {s: h.to_dict() for s, h in self.holdings.items()},
            "history": self.history,
            "cooldowns": self.cooldowns,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaperAccount":
        if not data:
            return cls()
        return cls(
            cash=data.get("cash", DEFAULT_CAPITAL),
            initial_capital=data.get("initial_capital", DEFAULT_CAPITAL),
            holdings={s: Holding(**h) for s, h in data.get("holdings", {}).items()},
            history=data.get("history", []),
            cooldowns=data.get("cooldowns", {}),  # 구 데이터 호환
        )
