"""자녀 일회성 지원에 대한 간이 증여세 추정.

중요
- 증여세 납세의무자는 수증자인 자녀로 본다.
- 따라서 본 모듈의 세액은 *자녀 부담 추정치*이며 A씨 가구 현금유출에 더하지 않는다.
- 모델 내 일회성 자녀지원은 비혼독립 주거지원과 결혼주거지원 최대 2회뿐이다.
- 비혼독립 지원은 5천만원보다 작으므로, 후속 결혼지원 시 일반 증여재산공제
  사용액을 추적하는 단순화로 충분하도록 설계했다.
- 신고세액공제, 평가차이, 동일인 증여 합산의 세부 규정 등은 반영하지 않은
  재무설계용 간이 추정치다.
"""
from __future__ import annotations

GENERAL_LINEAL_ASCENDANT_DEDUCTION = 50_000_000
MARRIAGE_ADDITIONAL_DEDUCTION = 100_000_000


def progressive_gift_tax(tax_base: int) -> int:
    """2026년 일반 증여세율 기준 산출세액 단순 계산."""
    tax_base = max(0, int(tax_base))
    if tax_base <= 100_000_000:
        return round(tax_base * 0.10)
    if tax_base <= 500_000_000:
        return round(tax_base * 0.20 - 10_000_000)
    if tax_base <= 1_000_000_000:
        return round(tax_base * 0.30 - 60_000_000)
    if tax_base <= 3_000_000_000:
        return round(tax_base * 0.40 - 160_000_000)
    return round(tax_base * 0.50 - 460_000_000)


def estimate_child_gift_tax(
    gift_amount: int,
    year: int,
    prior_gifts: list[dict],
    marriage_event: bool,
):
    """현재 지원금에 대한 간이 증여세와 공제 사용내역을 반환."""
    gift_amount = max(0, int(gift_amount))

    # 연 단위 엔진이므로 '직전 10개 연도'의 실제 지원액을 일반공제 사용이력으로 추적.
    recent_prior = [
        g for g in prior_gifts
        if year - 10 < g["year"] <= year
    ]
    prior_general_used = min(
        GENERAL_LINEAL_ASCENDANT_DEDUCTION,
        sum(int(g["amount"]) for g in recent_prior),
    )
    general_available = max(
        0,
        GENERAL_LINEAL_ASCENDANT_DEDUCTION - prior_general_used,
    )
    general_deduction = min(gift_amount, general_available)

    remaining = gift_amount - general_deduction
    marriage_deduction = 0
    if marriage_event:
        marriage_deduction = min(
            remaining,
            MARRIAGE_ADDITIONAL_DEDUCTION,
        )
        remaining -= marriage_deduction

    tax_base = max(0, remaining)
    tax = progressive_gift_tax(tax_base)

    return {
        "gift_amount": gift_amount,
        "general_deduction_used": general_deduction,
        "marriage_deduction_used": marriage_deduction,
        "tax_base": tax_base,
        "estimated_gift_tax_child": tax,
        "child_net_after_gift_tax": gift_amount - tax,
        "tax_payer": "child",
        "household_cash_outflow_for_tax": 0,
    }
