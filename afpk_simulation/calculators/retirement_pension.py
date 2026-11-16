"""팀원 제공 '퇴직연금.py'의 계산 함수 모음.
원본 계산식은 변경하지 않고 노트북 예제 및 자동 실행만 제거함.
"""

POLICY = {'policy_year': 2026, 'minimum_pension_age': 55, 'retirement_income_5yr_exception': True, 'annual_limit_multiplier': 1.2, 'limit_exempt_from_year': 11, 'tax_reduction_by_actual_receipt_year': {'years_1_to_10': 0.7, 'years_11_to_20': 0.6, 'years_21_plus': 0.5}, 'local_income_tax_rate': 0.1, 'investment_return_rate': 0.0}
PEOPLE = {'A씨': {'current_age': 57, 'retirement_age': 66, 'gross_retirement_benefit': 69800000, 'lump_sum_national_tax': 131200, 'pension_start_age': 66, 'payout_years': 20, 'payment_frequency': 'annual'}, '배우자': {'current_age': 59, 'retirement_age': 66, 'gross_retirement_benefit': 116890000, 'lump_sum_national_tax': 821360, 'pension_start_age': 66, 'payout_years': 20, 'payment_frequency': 'annual'}}
import pandas as pd

def tax_multiplier(actual_receipt_year, policy=POLICY):
    if actual_receipt_year <= 10:
        return policy['tax_reduction_by_actual_receipt_year']['years_1_to_10']
    elif actual_receipt_year <= 20:
        return policy['tax_reduction_by_actual_receipt_year']['years_11_to_20']
    else:
        return policy['tax_reduction_by_actual_receipt_year']['years_21_plus']

def pension_receipt_limit(balance, pension_receipt_year, policy=POLICY):
    if pension_receipt_year >= policy['limit_exempt_from_year']:
        return float('inf')
    denominator = 11 - pension_receipt_year
    return balance / denominator * policy['annual_limit_multiplier']

def build_irp_pension_schedule(gross_retirement_benefit, lump_sum_national_tax, pension_start_age, payout_years, payment_frequency='annual', policy=POLICY):
    if pension_start_age < policy['minimum_pension_age']:
        raise ValueError(f"연금수령 시작연령은 {policy['minimum_pension_age']}세 이상이어야 합니다.")
    if payout_years <= 0:
        raise ValueError('수령기간은 1년 이상이어야 합니다.')
    if payment_frequency not in ('annual', 'monthly'):
        raise ValueError("payment_frequency는 'annual' 또는 'monthly'만 가능합니다.")
    starting_balance = float(gross_retirement_benefit)
    lump_sum_effective_tax_rate = lump_sum_national_tax / gross_retirement_benefit if gross_retirement_benefit > 0 else 0
    planned_annual_withdrawal = starting_balance / payout_years
    balance = starting_balance
    rows = []
    for year_no in range(1, payout_years + 1):
        age = pension_start_age + year_no - 1
        opening_balance = balance
        annual_limit = pension_receipt_limit(opening_balance, year_no, policy)
        planned = min(planned_annual_withdrawal, opening_balance)
        pension_withdrawal = min(planned, annual_limit)
        non_pension_withdrawal = max(0, planned - pension_withdrawal)
        multiplier = tax_multiplier(year_no, policy)
        pension_national_tax = pension_withdrawal * lump_sum_effective_tax_rate * multiplier
        non_pension_national_tax = non_pension_withdrawal * lump_sum_effective_tax_rate
        national_tax = pension_national_tax + non_pension_national_tax
        local_tax = national_tax * policy['local_income_tax_rate']
        total_tax = national_tax + local_tax
        gross_withdrawal = pension_withdrawal + non_pension_withdrawal
        net_withdrawal = gross_withdrawal - total_tax
        balance = opening_balance - gross_withdrawal
        if payment_frequency == 'monthly':
            monthly_gross = gross_withdrawal / 12
            monthly_net = net_withdrawal / 12
        else:
            monthly_gross = None
            monthly_net = None
        rows.append({'수령연차': year_no, '나이': age, '기초 IRP잔액': round(opening_balance), '연금수령한도': None if annual_limit == float('inf') else round(annual_limit), '연금수령분': round(pension_withdrawal), '연금외수령분': round(non_pension_withdrawal), '세금감면계수': multiplier, '국세': round(national_tax), '지방소득세': round(local_tax), '총세금': round(total_tax), '세전수령액': round(gross_withdrawal), '세후수령액': round(net_withdrawal), '월세전수령액': None if monthly_gross is None else round(monthly_gross), '월세후수령액': None if monthly_net is None else round(monthly_net), '기말 IRP잔액': round(balance)})
    df = pd.DataFrame(rows)
    summary = {'총 세전수령액': round(df['세전수령액'].sum()), '총 국세': round(df['국세'].sum()), '총 지방소득세': round(df['지방소득세'].sum()), '총 세금': round(df['총세금'].sum()), '총 세후수령액': round(df['세후수령액'].sum()), '최종 IRP잔액': round(df['기말 IRP잔액'].iloc[-1])}
    return (df, summary)

def compare_payout_periods(person, periods=(10, 15, 20)):
    rows = []
    for years in periods:
        df, summary = build_irp_pension_schedule(gross_retirement_benefit=person['gross_retirement_benefit'], lump_sum_national_tax=person['lump_sum_national_tax'], pension_start_age=person['pension_start_age'], payout_years=years, payment_frequency='annual')
        rows.append({'수령기간': f'{years}년', '연평균 세전수령액': round(df['세전수령액'].mean()), '연평균 세후수령액': round(df['세후수령액'].mean()), '총 세금': summary['총 세금'], '총 세후수령액': summary['총 세후수령액'], '연금외수령 발생여부': bool((df['연금외수령분'] > 0).any())})
    return pd.DataFrame(rows)
