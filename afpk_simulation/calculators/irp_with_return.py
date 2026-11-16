"""IRP 연금수령 스케줄 — 잔액 운용수익률 반영 버전.

팀원 계산기 build_irp_pension_schedule()는 잔액 운용수익률이 0%로 고정되어 있다
(POLICY['investment_return_rate']=0.0이 정의만 되어 있고 계산에 쓰이지 않음).
이 모듈은 원본 함수를 수정하지 않고, 운용수익률이 있는 경우의 스케줄을 계산한다.
annual_return=0이면 원본 함수 결과를 그대로 반환한다(결과 동일 보장).

가정
- 매년 연초에 '잔액 ÷ 남은 연수'를 인출하고, 남은 잔액이 그해 annual_return으로 불어난다.
  (수익률 0%이면 원본의 '총액 ÷ 수령연수'와 같다.)
- 인출 순서(소득세법): 이연퇴직소득(원금) → 운용수익.
- 원금 부분: 원본과 같은 퇴직소득세 방식(실효세율 × 연차별 감면계수, 연금외수령은 감면 없음) + 지방세 10%.
- 운용수익 부분: 연금수령분은 연금소득세(지방세 포함) 수령 나이 70세 미만 5.5%, 70~79세 4.4%,
  80세 이상 3.3%로 분리과세. 연금외수령분은 기타소득세 16.5%.
  (사적연금 연 1,500만 원 초과 시 종합과세 선택 등은 반영하지 않음 — 운용수익 인출액이 작아 영향 미미)
- 운용보수는 반영하지 않음.
"""
from __future__ import annotations

import pandas as pd

from calculators.retirement_pension import (
    POLICY, build_irp_pension_schedule, pension_receipt_limit, tax_multiplier,
)

OTHER_INCOME_TAX_RATE = 0.165


def pension_income_tax_rate(age: int) -> float:
    """사적연금 연금소득세율(지방소득세 포함)."""
    if age < 70:
        return 0.055
    if age < 80:
        return 0.044
    return 0.033


def build_irp_schedule_with_return(
    gross_retirement_benefit,
    lump_sum_national_tax,
    pension_start_age,
    payout_years,
    annual_return=0.0,
    policy=POLICY,
):
    if annual_return == 0:
        return build_irp_pension_schedule(
            gross_retirement_benefit=gross_retirement_benefit,
            lump_sum_national_tax=lump_sum_national_tax,
            pension_start_age=pension_start_age,
            payout_years=payout_years,
            payment_frequency='annual',
            policy=policy,
        )
    if not -0.5 < annual_return < 0.5:
        raise ValueError('IRP 운용수익률은 소수로 입력하세요 (예: 3.32% → 0.0332).')
    if pension_start_age < policy['minimum_pension_age']:
        raise ValueError(f"연금수령 시작연령은 {policy['minimum_pension_age']}세 이상이어야 합니다.")
    if payout_years <= 0:
        raise ValueError('수령기간은 1년 이상이어야 합니다.')

    eff = lump_sum_national_tax / gross_retirement_benefit if gross_retirement_benefit > 0 else 0
    balance = float(gross_retirement_benefit)
    principal = float(gross_retirement_benefit)   # 남은 이연퇴직소득
    rows = []
    for year_no in range(1, payout_years + 1):
        age = pension_start_age + year_no - 1
        opening = balance
        remaining = payout_years - year_no + 1
        planned = opening / remaining
        limit = pension_receipt_limit(opening, year_no, policy)
        pension_w = min(planned, limit)
        non_pension_w = max(0.0, planned - pension_w)

        # 원금(이연퇴직소득) 먼저 인출
        p_pen = min(pension_w, principal)
        g_pen = pension_w - p_pen
        p_non = min(non_pension_w, principal - p_pen)
        g_non = non_pension_w - p_non
        principal -= p_pen + p_non

        mult = tax_multiplier(year_no, policy)
        national = p_pen * eff * mult + p_non * eff
        local = national * policy['local_income_tax_rate']
        gain_tax = g_pen * pension_income_tax_rate(age) + g_non * OTHER_INCOME_TAX_RATE
        total_tax = national + local + gain_tax

        remainder = opening - planned
        growth = remainder * annual_return
        balance = remainder + growth
        rows.append({
            '수령연차': year_no, '나이': age, '기초 IRP잔액': round(opening),
            '연금수령한도': None if limit == float('inf') else round(limit),
            '연금수령분': round(pension_w), '연금외수령분': round(non_pension_w),
            '원금인출': round(p_pen + p_non), '운용수익인출': round(g_pen + g_non),
            '세금감면계수': mult, '국세': round(national), '지방소득세': round(local),
            '운용수익세': round(gain_tax), '총세금': round(total_tax),
            '세전수령액': round(planned), '세후수령액': round(planned - total_tax),
            '운용수익': round(growth), '기말 IRP잔액': round(balance),
        })
    df = pd.DataFrame(rows)
    summary = {
        '총 세전수령액': round(df['세전수령액'].sum()),
        '총 세금': round(df['총세금'].sum()),
        '총 세후수령액': round(df['세후수령액'].sum()),
        '총 운용수익': round(df['운용수익'].sum()),
        '최종 IRP잔액': round(df['기말 IRP잔액'].iloc[-1]),
    }
    return df, summary
