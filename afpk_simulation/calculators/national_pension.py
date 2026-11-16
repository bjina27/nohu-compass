"""국민연금 계산기: 팀원 최종본에서 계산 함수와 입력 이력만 분리한 라이브러리.

원본: 국민연금계산기_완성본.py (2026 제도 및 세법 가정)
노트북 display / print / assert 등의 실행 예제는 가져오지 않았음.
기존 직장 66세 연말퇴직 가정은 AFPK engine.py와 달라 통합 어댑터가
실제 engine.py 급여와 퇴직연도 규칙을 우선 적용한다.
"""
import pandas as pd

A_VALUE_2026 = 3193511

POLICY_2026 = {'reference_year': 2026, 'a_value': A_VALUE_2026, 'min_contribution_months': 120, 'early_reduction_per_month': 0.005, 'early_max_months': 60, 'defer_bonus_per_month': 0.006, 'defer_max_months': 60, 'dependent_spouse_annual': 306630, 'dependent_child_parent_annual': 204360}

REVALUATION_2026 = {1988: 8.528, 1989: 7.54, 1990: 6.565, 1991: 5.489, 1992: 4.763, 1993: 4.217, 1994: 3.714, 1995: 3.429, 1996: 3.145, 1997: 2.843, 1998: 2.533, 1999: 2.474, 2000: 2.511, 2001: 2.467, 2002: 2.419, 2003: 2.261, 2004: 2.132, 2005: 2.039, 2006: 1.973, 2007: 1.904, 2008: 1.824, 2009: 1.782, 2010: 1.751, 2011: 1.688, 2012: 1.65, 2013: 1.611, 2014: 1.562, 2015: 1.517, 2016: 1.467, 2017: 1.407, 2018: 1.355, 2019: 1.31, 2020: 1.257, 2021: 1.191, 2022: 1.116, 2023: 1.068, 2024: 1.034, 2025: 1.0, 2026: 1.0, 2027: 1.0, 2028: 1.0}

def pension_coefficient(year: int) -> float:
    if 1988 <= year <= 1998:
        return 2.4
    elif 1999 <= year <= 2007:
        return 1.8
    elif 2008 <= year <= 2025:
        return 1.5 - 0.015 * (year - 2008)
    elif year >= 2026:
        return 1.29
    else:
        raise ValueError('국민연금 도입 이전 연도는 계산할 수 없습니다.')

def normal_pension_age(birth_year: int) -> int:
    if birth_year <= 1952:
        return 60
    elif birth_year <= 1956:
        return 61
    elif birth_year <= 1960:
        return 62
    elif birth_year <= 1964:
        return 63
    elif birth_year <= 1968:
        return 64
    return 65

def earliest_early_age(birth_year: int) -> int:
    return normal_pension_age(birth_year) - 5

def prepare_history(income_history):
    df = pd.DataFrame(income_history).copy()
    required = {'year', 'monthly_income', 'months'}
    if not required.issubset(df.columns):
        raise ValueError(f'필수 열: {required}')
    df['year'] = df['year'].astype(int)
    df['monthly_income'] = df['monthly_income'].astype(float)
    df['months'] = df['months'].astype(int)
    if (df['months'] < 1).any() or (df['months'] > 12).any():
        raise ValueError('months는 1~12 사이여야 합니다.')
    if (df['monthly_income'] < 0).any():
        raise ValueError('monthly_income은 0 이상이어야 합니다.')
    missing = [y for y in df['year'].unique() if y not in REVALUATION_2026]
    if missing:
        raise ValueError(f'재평가율이 없는 연도: {missing}')
    df['revaluation_rate'] = df['year'].map(REVALUATION_2026)
    df['revalued_monthly_income'] = df['monthly_income'] * df['revaluation_rate']
    return df.sort_values('year').reset_index(drop=True)

def calculate_b_value(income_history):
    df = prepare_history(income_history)
    total_months = int(df['months'].sum())
    if total_months == 0:
        raise ValueError('가입월수가 0입니다.')
    b = (df['revalued_monthly_income'] * df['months']).sum() / total_months
    return (b, total_months, df)

def old_age_payment_rate(total_months: int) -> float:
    if total_months < 120:
        return 0.0
    rate = 0.5 + (total_months - 120) * (0.05 / 12)
    return min(rate, 1.0)

def calculate_normal_pension_from_history(income_history, a_value=A_VALUE_2026, dependent_annual=0):
    b, total_months, df = calculate_b_value(income_history)
    if total_months < POLICY_2026['min_contribution_months']:
        return {'eligible': False, 'reason': '가입기간 10년 미만', 'B': b, 'total_months': total_months}
    P = total_months
    weighted_sum = 0.0
    for _, row in df.iterrows():
        year = int(row['year'])
        months = int(row['months'])
        c = pension_coefficient(year)
        if year <= 1998:
            base_component = c * (a_value + 0.75 * b)
        else:
            base_component = c * (a_value + b)
        weighted_sum += base_component * (months / P)
    n = max(P - 240, 0)
    long_service_factor = 1 + 0.05 * n / 12
    payment_rate = old_age_payment_rate(P)
    basic_annual = weighted_sum * long_service_factor
    pension_annual = basic_annual * payment_rate + dependent_annual
    pension_monthly = pension_annual / 12
    return {'eligible': True, 'A': a_value, 'B': b, 'total_months': P, 'total_years': P / 12, 'n_over_20_months': n, 'long_service_factor': long_service_factor, 'payment_rate': payment_rate, 'basic_annual': basic_annual, 'normal_annual_pension': pension_annual, 'normal_monthly_pension': pension_monthly, 'history_detail': df}

def apply_claim_timing(normal_monthly_pension: float, birth_year: int, claim_age: int, claim_month: int=0, monthly_income_amount=None, policy=POLICY_2026):
    if not 0 <= claim_month <= 11:
        raise ValueError('claim_month는 0~11이어야 합니다.')
    normal_age = normal_pension_age(birth_year)
    normal_m = normal_age * 12
    claim_m = claim_age * 12 + claim_month
    diff = claim_m - normal_m
    if diff < 0:
        months = -diff
        if months > policy['early_max_months']:
            raise ValueError('조기수령은 최대 5년(60개월)까지 가능합니다.')
        adj_rate = -months * policy['early_reduction_per_month']
        adjusted = normal_monthly_pension * (1 + adj_rate)
        if monthly_income_amount is None:
            early_income_ok = None
            eligibility_note = '조기수령 소득요건 미확인'
        else:
            early_income_ok = monthly_income_amount <= policy['a_value']
            eligibility_note = '조기수령 가능' if early_income_ok else '소득요건상 조기수령 불가'
        claim_type = '조기수령'
    elif diff == 0:
        adj_rate = 0.0
        adjusted = normal_monthly_pension
        early_income_ok = None
        eligibility_note = '정상수령'
        claim_type = '정상수령'
    else:
        months = diff
        if months > policy['defer_max_months']:
            raise ValueError('연기수령 가산은 최대 5년(60개월)까지만 계산합니다.')
        adj_rate = months * policy['defer_bonus_per_month']
        adjusted = normal_monthly_pension * (1 + adj_rate)
        early_income_ok = None
        eligibility_note = '연기수령'
        claim_type = '연기수령'
    return {'birth_year': birth_year, 'normal_age': normal_age, 'claim_age': claim_age, 'claim_month': claim_month, 'claim_type': claim_type, 'adjustment_rate': adj_rate, 'normal_monthly_pension': round(normal_monthly_pension), 'adjusted_monthly_pension': round(adjusted), 'adjusted_annual_pension': round(adjusted * 12), 'early_income_ok': early_income_ok, 'eligibility_note': eligibility_note}

def nps_calculator(birth_year: int, income_history, claim_age: int | None=None, claim_month: int=0, monthly_income_amount=None, dependent_annual=0):
    normal = calculate_normal_pension_from_history(income_history=income_history, a_value=A_VALUE_2026, dependent_annual=dependent_annual)
    if not normal['eligible']:
        return {'normal': normal, 'claim': None}
    if claim_age is None:
        claim_age = normal_pension_age(birth_year)
    claim = apply_claim_timing(normal_monthly_pension=normal['normal_monthly_pension'], birth_year=birth_year, claim_age=claim_age, claim_month=claim_month, monthly_income_amount=monthly_income_amount)
    return {'normal': normal, 'claim': claim}

def print_result(result):
    normal = result['normal']
    claim = result['claim']
    if not normal['eligible']:
        print('수급권 없음:', normal['reason'])
        return
    print('=' * 68)
    print('국민연금 계산 결과 (2026년 현재가치 기준)')
    print('=' * 68)
    print(f"A값                        : {normal['A']:,.0f}원")
    print(f"B값                        : {normal['B']:,.0f}원")
    print(f"총 가입기간                 : {normal['total_years']:.2f}년 ({normal['total_months']}개월)")
    print(f"20년 초과 가입월수(n)       : {normal['n_over_20_months']}개월")
    print(f"장기가입 가산계수            : {normal['long_service_factor']:.4f}")
    print(f"노령연금 지급률              : {normal['payment_rate'] * 100:.1f}%")
    print(f"정상수령 예상 월액           : {normal['normal_monthly_pension']:,.0f}원")
    print('-' * 68)
    print(f"정상 수급개시연령            : {claim['normal_age']}세")
    print(f"선택 수령개시               : {claim['claim_age']}세 {claim['claim_month']}개월")
    print(f"수령유형                    : {claim['claim_type']}")
    print(f"조정률                      : {claim['adjustment_rate'] * 100:+.1f}%")
    print(f"최종 예상 월액              : {claim['adjusted_monthly_pension']:,.0f}원")
    print(f"최종 예상 연액              : {claim['adjusted_annual_pension']:,.0f}원")
    print(f"판정 메모                   : {claim['eligibility_note']}")
    print('=' * 68)

a_income_history = [{'year': 1993, 'monthly_income': 548000, 'months': 12}, {'year': 1994, 'monthly_income': 765000, 'months': 12}, {'year': 1995, 'monthly_income': 892000, 'months': 12}, {'year': 1996, 'monthly_income': 978000, 'months': 12}, {'year': 1997, 'monthly_income': 1093000, 'months': 12}, {'year': 1998, 'monthly_income': 1072000, 'months': 12}, {'year': 2007, 'monthly_income': 1604000, 'months': 12}, {'year': 2008, 'monthly_income': 1362000, 'months': 12}, {'year': 2009, 'monthly_income': 1267000, 'months': 12}, {'year': 2010, 'monthly_income': 1309000, 'months': 12}, {'year': 2011, 'monthly_income': 1386000, 'months': 12}, {'year': 2012, 'monthly_income': 1479000, 'months': 12}, {'year': 2013, 'monthly_income': 1561000, 'months': 12}, {'year': 2014, 'monthly_income': 1530000, 'months': 12}, {'year': 2015, 'monthly_income': 1558000, 'months': 12}, {'year': 2016, 'monthly_income': 1668000, 'months': 12}, {'year': 2017, 'monthly_income': 1752000, 'months': 12}, {'year': 2018, 'monthly_income': 1867000, 'months': 12}, {'year': 2019, 'monthly_income': 1976000, 'months': 12}, {'year': 2020, 'monthly_income': 2000000, 'months': 12}, {'year': 2021, 'monthly_income': 2050000, 'months': 12}, {'year': 2022, 'monthly_income': 2200000, 'months': 12}, {'year': 2023, 'monthly_income': 2361000, 'months': 12}, {'year': 2024, 'monthly_income': 2300000, 'months': 12}, {'year': 2025, 'monthly_income': 2420000, 'months': 12}, {'year': 2026, 'monthly_income': 2310000, 'months': 12}, {'year': 2027, 'monthly_income': 2310000, 'months': 12}, {'year': 2028, 'monthly_income': 2310000, 'months': 12}]

spouse_income_history = [{'year': 1994, 'monthly_income': 936000, 'months': 12}, {'year': 1995, 'monthly_income': 1036000, 'months': 12}, {'year': 1996, 'monthly_income': 1143000, 'months': 12}, {'year': 1997, 'monthly_income': 1583000, 'months': 12}, {'year': 1998, 'monthly_income': 1553000, 'months': 12}, {'year': 1999, 'monthly_income': 1546000, 'months': 12}, {'year': 2000, 'monthly_income': 1665000, 'months': 12}, {'year': 2001, 'monthly_income': 1741000, 'months': 12}, {'year': 2002, 'monthly_income': 2235000, 'months': 12}, {'year': 2003, 'monthly_income': 2409000, 'months': 12}, {'year': 2004, 'monthly_income': 2589000, 'months': 12}, {'year': 2005, 'monthly_income': 2750000, 'months': 12}, {'year': 2006, 'monthly_income': 2911000, 'months': 12}, {'year': 2007, 'monthly_income': 3201000, 'months': 12}, {'year': 2008, 'monthly_income': 2800000, 'months': 12}, {'year': 2009, 'monthly_income': 2837000, 'months': 12}, {'year': 2010, 'monthly_income': 2876000, 'months': 12}, {'year': 2011, 'monthly_income': 2922000, 'months': 12}, {'year': 2012, 'monthly_income': 3010000, 'months': 12}, {'year': 2013, 'monthly_income': 3106000, 'months': 12}, {'year': 2014, 'monthly_income': 3154000, 'months': 12}, {'year': 2015, 'monthly_income': 3300000, 'months': 12}, {'year': 2016, 'monthly_income': 3470000, 'months': 12}, {'year': 2017, 'monthly_income': 3247000, 'months': 12}, {'year': 2018, 'monthly_income': 3400000, 'months': 12}, {'year': 2019, 'monthly_income': 3557000, 'months': 12}, {'year': 2020, 'monthly_income': 3600000, 'months': 12}, {'year': 2021, 'monthly_income': 3768000, 'months': 12}, {'year': 2022, 'monthly_income': 3625000, 'months': 12}, {'year': 2023, 'monthly_income': 3658000, 'months': 12}, {'year': 2024, 'monthly_income': 3855000, 'months': 12}, {'year': 2025, 'monthly_income': 4078000, 'months': 12}, {'year': 2026, 'monthly_income': 3940000, 'months': 12}]

TAX_POLICY_2026 = {'basic_deduction_per_person': 1500000, 'standard_tax_credit': 70000, 'local_income_tax_rate': 0.1}

def pension_taxable_ratio(income_history):
    """
    국민연금 과세기준금액 비율:
    2002년 이후 납입기간의 환산소득 누계액 / 총 납입기간의 환산소득 누계액

    환산소득 = 기준소득월액 × 해당연도 재평가율 × 가입개월수
    """
    df = prepare_history(income_history)
    total_revalued_income = (df['revalued_monthly_income'] * df['months']).sum()
    post_2002_revalued_income = (df.loc[df['year'] >= 2002, 'revalued_monthly_income'] * df.loc[df['year'] >= 2002, 'months']).sum()
    if total_revalued_income <= 0:
        raise ValueError('총 환산소득 누계액은 0보다 커야 합니다.')
    return post_2002_revalued_income / total_revalued_income

def pension_income_deduction(gross_taxable_pension):
    """연금소득공제(한도 900만원)."""
    x = max(0, float(gross_taxable_pension))
    if x <= 3500000:
        deduction = x
    elif x <= 7000000:
        deduction = 3500000 + (x - 3500000) * 0.4
    elif x <= 14000000:
        deduction = 4900000 + (x - 7000000) * 0.2
    else:
        deduction = 6300000 + (x - 14000000) * 0.1
    return min(deduction, 9000000)

def comprehensive_income_tax(tax_base):
    """2026년 종합소득 기본세율에 따른 산출세액."""
    x = max(0, float(tax_base))
    brackets = [(14000000, 0.06, 0), (50000000, 0.15, 1260000), (88000000, 0.24, 5760000), (150000000, 0.35, 15440000), (300000000, 0.38, 19940000), (500000000, 0.4, 25940000), (1000000000, 0.42, 35940000), (float('inf'), 0.45, 65940000)]
    for upper, rate, quick_deduction in brackets:
        if x <= upper:
            return x * rate - quick_deduction
    raise RuntimeError('세율 계산 오류')

def first_year_payment_months(birth_month, claim_month=None):
    """
    정상 노령연금 기준:
    지급개시연령 생일이 속한 달의 다음 달부터 지급.
    예: 6월생 -> 7~12월 = 첫해 6개월.

    claim_month를 직접 지정하면 해당 월의 다음 달부터 지급하는 단순 월단위 계산에 사용.
    """
    if not 1 <= birth_month <= 12:
        raise ValueError('birth_month는 1~12 사이여야 합니다.')
    trigger_month = birth_month if claim_month is None else claim_month
    if not 1 <= trigger_month <= 12:
        raise ValueError('claim_month는 1~12 사이여야 합니다.')
    return 12 - trigger_month

def calculate_after_tax_nps(monthly_pension, income_history, dependent_count=0, months_received=12):
    """
    다른 종합소득이 없는 국민연금 수급자의 2026년 기준 연금소득 연말정산 추정.

    dependent_count:
        본인을 제외한 세법상 기본공제 대상자 수.
        본인 1명은 자동 포함.

    months_received:
        해당 과세연도 실제 연금 수령 개월 수.
        정상수령 첫해는 birth_month에 따라 계산 가능.
    """
    if dependent_count < 0 or int(dependent_count) != dependent_count:
        raise ValueError('dependent_count는 0 이상의 정수여야 합니다.')
    if not 0 <= months_received <= 12:
        raise ValueError('months_received는 0~12 사이여야 합니다.')
    annual_pension_received = float(monthly_pension) * months_received
    taxable_ratio = pension_taxable_ratio(income_history)
    taxable_pension = annual_pension_received * taxable_ratio
    pension_deduction = pension_income_deduction(taxable_pension)
    pension_income = max(0, taxable_pension - pension_deduction)
    basic_deduction = TAX_POLICY_2026['basic_deduction_per_person'] * (1 + dependent_count)
    tax_base = max(0, pension_income - basic_deduction)
    calculated_income_tax = max(0, comprehensive_income_tax(tax_base))
    standard_credit = min(calculated_income_tax, TAX_POLICY_2026['standard_tax_credit'])
    income_tax = max(0, calculated_income_tax - standard_credit)
    local_income_tax = income_tax * TAX_POLICY_2026['local_income_tax_rate']
    total_tax = income_tax + local_income_tax
    net_annual_pension = annual_pension_received - total_tax
    net_monthly_equivalent = net_annual_pension / months_received if months_received > 0 else 0
    return {'months_received': months_received, 'gross_annual_pension': annual_pension_received, 'taxable_ratio': taxable_ratio, 'taxable_pension': taxable_pension, 'pension_income_deduction': pension_deduction, 'pension_income': pension_income, 'dependent_count_excluding_self': int(dependent_count), 'basic_deduction': basic_deduction, 'tax_base': tax_base, 'calculated_income_tax': calculated_income_tax, 'standard_tax_credit': standard_credit, 'income_tax': income_tax, 'local_income_tax': local_income_tax, 'total_tax': total_tax, 'net_annual_pension': net_annual_pension, 'net_monthly_equivalent': net_monthly_equivalent}

BIRTH_MONTH_A = 6

BIRTH_MONTH_SPOUSE = 6

DEPENDENT_COUNT_A = 0

DEPENDENT_COUNT_SPOUSE = 0

def print_tax_result(name, result):
    print('=' * 72)
    print(f'{name} 국민연금 세후 계산')
    print('=' * 72)
    print(f"해당연도 수령개월            : {result['months_received']}개월")
    print(f"세전 연금수령액              : {result['gross_annual_pension']:,.0f}원")
    print(f"과세대상 비율                : {result['taxable_ratio'] * 100:.2f}%")
    print(f"과세대상 연금액              : {result['taxable_pension']:,.0f}원")
    print(f"연금소득공제                 : {result['pension_income_deduction']:,.0f}원")
    print(f"연금소득금액                 : {result['pension_income']:,.0f}원")
    print(f"본인 외 기본공제 대상자 수   : {result['dependent_count_excluding_self']}명")
    print(f"기본공제                     : {result['basic_deduction']:,.0f}원")
    print(f"과세표준                     : {result['tax_base']:,.0f}원")
    print(f"산출세액                     : {result['calculated_income_tax']:,.0f}원")
    print(f"표준세액공제                 : {result['standard_tax_credit']:,.0f}원")
    print(f"소득세                       : {result['income_tax']:,.0f}원")
    print(f"지방소득세                   : {result['local_income_tax']:,.0f}원")
    print(f"총 세금                      : {result['total_tax']:,.0f}원")
    print(f"세후 연금수령액(연)          : {result['net_annual_pension']:,.0f}원")
    print(f"세후 월환산액                : {result['net_monthly_equivalent']:,.0f}원")
    print('=' * 72)

def earned_income_deduction(gross_salary):
    """2026년 근로소득공제. 공제한도 2,000만원."""
    x = max(0.0, float(gross_salary))
    if x <= 5000000:
        d = x * 0.7
    elif x <= 15000000:
        d = 3500000 + (x - 5000000) * 0.4
    elif x <= 45000000:
        d = 7500000 + (x - 15000000) * 0.15
    elif x <= 100000000:
        d = 12000000 + (x - 45000000) * 0.05
    else:
        d = 14750000 + (x - 100000000) * 0.02
    return min(d, 20000000, x)

def earned_income_tax_credit_limit(gross_salary):
    """2026년 근로소득세액공제 한도."""
    x = max(0.0, float(gross_salary))
    if x <= 33000000:
        return 740000
    elif x <= 70000000:
        return max(660000, 740000 - (x - 33000000) * 0.008)
    elif x <= 120000000:
        return max(500000, 660000 - (x - 70000000) * 0.5)
    else:
        return max(200000, 500000 - (x - 120000000) * 0.5)

def earned_income_tax_credit(calculated_income_tax, earned_income_amount, comprehensive_income_amount, gross_salary):
    """
    다른 종합소득이 있는 경우 근로소득에 대응하는 종합소득산출세액을
    전체 산출세액 × (근로소득금액 / 종합소득금액)으로 배분하여 계산.
    """
    if comprehensive_income_amount <= 0 or earned_income_amount <= 0:
        return 0.0
    earned_tax_portion = calculated_income_tax * earned_income_amount / comprehensive_income_amount
    if earned_tax_portion <= 1300000:
        credit = earned_tax_portion * 0.55
    else:
        credit = 715000 + (earned_tax_portion - 1300000) * 0.3
    return min(credit, earned_income_tax_credit_limit(gross_salary))

def calculate_combined_wage_pension_tax(gross_salary, monthly_pension, income_history, pension_months=12, dependent_count=0, other_income_deductions=0, other_tax_credits=0, use_standard_tax_credit=True):
    """
    근로소득 + 국민연금이 동시에 있는 연도의 단순화된 종합소득세 계산.

    Parameters
    ----------
    gross_salary : 연간 총급여액(비과세소득 제외 기준을 권장)
    monthly_pension : 해당 연도의 실제 월 국민연금 지급액
    income_history : 국민연금 과세대상비율 계산용 가입소득 이력
    pension_months : 해당 연도 실제 연금수령개월 수
    dependent_count : 본인을 제외한 기본공제 대상자 수
    other_income_deductions : 보험료 등 추가 소득공제액
    other_tax_credits : 추가 세액공제액
    use_standard_tax_credit : 특별공제를 별도로 반영하지 않는 경우 13만원 표준세액공제 적용

    주의
    ----
    건강보험료/고용보험료/의료비/신용카드 등 실제 개인별 공제항목은
    값이 주어지지 않으면 임의 추정하지 않는다.
    """
    if dependent_count < 0 or int(dependent_count) != dependent_count:
        raise ValueError('dependent_count는 0 이상의 정수여야 합니다.')
    if not 0 <= pension_months <= 12:
        raise ValueError('pension_months는 0~12 사이여야 합니다.')
    gross_salary = max(0.0, float(gross_salary))
    earned_deduction = earned_income_deduction(gross_salary)
    earned_income_amount = max(0.0, gross_salary - earned_deduction)
    gross_pension = float(monthly_pension) * pension_months
    taxable_ratio = pension_taxable_ratio(income_history)
    taxable_pension = gross_pension * taxable_ratio
    pension_deduction = pension_income_deduction(taxable_pension)
    pension_income_amount = max(0.0, taxable_pension - pension_deduction)
    comprehensive_income_amount = earned_income_amount + pension_income_amount
    basic_deduction = TAX_POLICY_2026['basic_deduction_per_person'] * (1 + dependent_count)
    total_income_deductions = basic_deduction + max(0.0, float(other_income_deductions))
    tax_base = max(0.0, comprehensive_income_amount - total_income_deductions)
    calculated_income_tax = max(0.0, comprehensive_income_tax(tax_base))
    earned_credit = earned_income_tax_credit(calculated_income_tax=calculated_income_tax, earned_income_amount=earned_income_amount, comprehensive_income_amount=comprehensive_income_amount, gross_salary=gross_salary)
    standard_credit = 130000 if use_standard_tax_credit else 0.0
    total_tax_credits = earned_credit + standard_credit + max(0.0, float(other_tax_credits))
    income_tax = max(0.0, calculated_income_tax - total_tax_credits)
    local_income_tax = income_tax * TAX_POLICY_2026['local_income_tax_rate']
    total_tax = income_tax + local_income_tax
    return {'gross_salary': gross_salary, 'earned_income_deduction': earned_deduction, 'earned_income_amount': earned_income_amount, 'gross_pension': gross_pension, 'pension_months': pension_months, 'pension_taxable_ratio': taxable_ratio, 'taxable_pension': taxable_pension, 'pension_income_deduction': pension_deduction, 'pension_income_amount': pension_income_amount, 'comprehensive_income_amount': comprehensive_income_amount, 'dependent_count_excluding_self': int(dependent_count), 'basic_deduction': basic_deduction, 'other_income_deductions': max(0.0, float(other_income_deductions)), 'tax_base': tax_base, 'calculated_income_tax': calculated_income_tax, 'earned_income_tax_credit': earned_credit, 'standard_tax_credit': standard_credit, 'other_tax_credits': max(0.0, float(other_tax_credits)), 'income_tax': income_tax, 'local_income_tax': local_income_tax, 'total_tax': total_tax, 'net_salary_plus_pension': gross_salary + gross_pension - total_tax}

def claim_age_comparison(normal_monthly_pension, birth_year):
    n_age = normal_pension_age(birth_year)
    rows = []
    for age in range(earliest_early_age(birth_year), n_age + 6):
        r = apply_claim_timing(normal_monthly_pension=normal_monthly_pension, birth_year=birth_year, claim_age=age)
        rows.append({'수령개시연령': age, '유형': r['claim_type'], '조정률': f"{r['adjustment_rate'] * 100:+.1f}%", '예상월액(원)': r['adjusted_monthly_pension'], '예상연액(원)': r['adjusted_annual_pension']})
    return pd.DataFrame(rows)

def pension_to_age_net(normal_monthly_pension, income_history, birth_year, birth_month, claim_age, dependent_count=0, end_age=100):
    """
    선택한 수령개시연령부터 end_age까지 연도별 세전/세후 국민연금 흐름 계산.

    가정
    - 기준연도(현재 2026)의 국민연금 제도 및 세법을 전 기간에 고정.
    - 첫 수령연도는 생일월 다음 달부터 연말까지의 개월 수만 지급.
    - 이후 연도는 12개월 지급.
    - 연금만 있는 경우의 연말정산 세액 기준.
    - 재취업 소득 및 재직자 감액은 별도 생애사건 모듈에서 처리.
    """
    timing = apply_claim_timing(normal_monthly_pension=normal_monthly_pension, birth_year=birth_year, claim_age=claim_age)
    adjusted_monthly = timing['adjusted_monthly_pension']
    start_age = claim_age
    rows = []
    cumulative_gross = 0.0
    cumulative_net = 0.0
    first_year_months = first_year_payment_months(birth_month)
    effective_first_payment_age = start_age if first_year_months > 0 else start_age + 1
    for age in range(start_age, end_age + 1):
        if age < effective_first_payment_age:
            months = 0
        elif age == start_age and first_year_months > 0:
            months = first_year_months
        else:
            months = 12
        if months == 0:
            tax_result = {'gross_annual_pension': 0.0, 'total_tax': 0.0, 'net_annual_pension': 0.0, 'taxable_ratio': pension_taxable_ratio(income_history)}
        else:
            tax_result = calculate_after_tax_nps(monthly_pension=adjusted_monthly, income_history=income_history, dependent_count=dependent_count, months_received=months)
        gross = tax_result['gross_annual_pension']
        net = tax_result['net_annual_pension']
        cumulative_gross += gross
        cumulative_net += net
        rows.append({'연령': age, '수령개월': months, '수령유형': timing['claim_type'], '세전월액(원)': adjusted_monthly if months > 0 else 0, '세전연액(원)': gross, '세금(원)': tax_result['total_tax'], '세후연액(원)': net, '세후월환산액(원)': net / months if months > 0 else 0, '세전누적액(원)': cumulative_gross, '세후누적액(원)': cumulative_net})
    return pd.DataFrame(rows)

def compare_claim_strategies_to_age100_net(normal_monthly_pension, income_history, birth_year, birth_month, dependent_count=0, end_age=100):
    """
    조기최대 / 정상 / 연기최대 전략의 100세까지 세후 누적 수령액 비교.
    """
    normal_age = normal_pension_age(birth_year)
    strategies = [('조기최대', earliest_early_age(birth_year)), ('정상', normal_age), ('연기최대', normal_age + 5)]
    rows = []
    for label, claim_age in strategies:
        flow = pension_to_age_net(normal_monthly_pension=normal_monthly_pension, income_history=income_history, birth_year=birth_year, birth_month=birth_month, claim_age=claim_age, dependent_count=dependent_count, end_age=end_age)
        timing = apply_claim_timing(normal_monthly_pension=normal_monthly_pension, birth_year=birth_year, claim_age=claim_age)
        rows.append({'전략': label, '수령개시연령': claim_age, '수령유형': timing['claim_type'], '조정률': timing['adjustment_rate'], '조정후 세전월액(원)': timing['adjusted_monthly_pension'], '100세까지 세전누적액(원)': flow['세전누적액(원)'].iloc[-1], '100세까지 세후누적액(원)': flow['세후누적액(원)'].iloc[-1]})
    return pd.DataFrame(rows)

EMPLOYMENT_ASSUMPTIONS = {'A씨': {'current_age': 57, 'current_monthly_salary': 2310000, 'annual_wage_growth': 0.0308, 'retirement_age': 66}, '배우자': {'current_age': 59, 'current_monthly_salary': 3940000, 'annual_wage_growth': 0.0083, 'retirement_age': 66}}

def monthly_salary_at_age(current_age, current_monthly_salary, annual_wage_growth, age):
    """
    DB 퇴직급여 계산에서 사용한 동일직장 임금상승률을 그대로 적용한 월급 추정.
    """
    if age < current_age:
        raise ValueError('age는 current_age 이상이어야 합니다.')
    years = age - current_age
    return current_monthly_salary * (1 + annual_wage_growth) ** years

def annual_salary_at_age(current_age, current_monthly_salary, annual_wage_growth, age, months_worked=12):
    """
    해당 연령에서의 기존 직장 연간 총급여 추정.
    현재 모델에서는 기본적으로 해당 연령 동안 12개월 근무로 둔다.
    퇴직연도 일부 근무만 반영하려면 months_worked를 조정할 수 있다.
    """
    if not 0 <= months_worked <= 12:
        raise ValueError('months_worked는 0~12 사이여야 합니다.')
    monthly = monthly_salary_at_age(current_age=current_age, current_monthly_salary=current_monthly_salary, annual_wage_growth=annual_wage_growth, age=age)
    return monthly * months_worked

def build_existing_job_salary_by_age(person_name, start_age, end_age=None):
    """
    기존 직장 근로소득 경로 생성.
    기본 종료연령은 retirement_age.
    """
    cfg = EMPLOYMENT_ASSUMPTIONS[person_name]
    retirement_age = cfg['retirement_age']
    if end_age is None:
        end_age = retirement_age
    rows = {}
    for age in range(start_age, end_age + 1):
        if age > retirement_age:
            break
        rows[age] = annual_salary_at_age(current_age=cfg['current_age'], current_monthly_salary=cfg['current_monthly_salary'], annual_wage_growth=cfg['annual_wage_growth'], age=age, months_worked=12)
    return rows

def combined_tax_during_existing_job(person_name, normal_monthly_pension, income_history, birth_year, birth_month, dependent_count=0):
    """
    정상 노령연금 개시연령부터 기존 직장 퇴직연령까지
    '현재 직장 근로소득 + 국민연금' 합산과세를 자동 계산.

    재취업 시나리오는 포함하지 않는다.
    """
    cfg = EMPLOYMENT_ASSUMPTIONS[person_name]
    normal_age = normal_pension_age(birth_year)
    retirement_age = cfg['retirement_age']
    salary_by_age = build_existing_job_salary_by_age(person_name=person_name, start_age=normal_age, end_age=retirement_age)
    rows = []
    for age in range(normal_age, retirement_age + 1):
        if age == normal_age:
            pension_months = first_year_payment_months(birth_month)
        else:
            pension_months = 12
        gross_salary = salary_by_age.get(age, 0.0)
        tax_result = calculate_combined_wage_pension_tax(gross_salary=gross_salary, monthly_pension=normal_monthly_pension, income_history=income_history, pension_months=pension_months, dependent_count=dependent_count, other_income_deductions=0, other_tax_credits=0, use_standard_tax_credit=True)
        rows.append({'연령': age, '기존직장 연간총급여(원)': gross_salary, '국민연금 수령개월': pension_months, '세전 국민연금(원)': tax_result['gross_pension'], '근로소득금액(원)': tax_result['earned_income_amount'], '연금소득금액(원)': tax_result['pension_income_amount'], '종합소득금액(원)': tax_result['comprehensive_income_amount'], '총세금(원)': tax_result['total_tax'], '세후 급여+연금 합계(원)': tax_result['net_salary_plus_pension']})
    return pd.DataFrame(rows)

def calculate_wage_only_tax(gross_salary, dependent_count=0, other_income_deductions=0, other_tax_credits=0, use_standard_tax_credit=True):
    """
    동일한 2026년 세법 가정으로 '근로소득만 있는 경우'의 세액 계산.
    연금 중복연도의 추가세액을 분리하기 위한 비교 기준이다.
    """
    gross_salary = max(0.0, float(gross_salary))
    earned_deduction = earned_income_deduction(gross_salary)
    earned_income_amount = max(0.0, gross_salary - earned_deduction)
    basic_deduction = TAX_POLICY_2026['basic_deduction_per_person'] * (1 + dependent_count)
    total_income_deductions = basic_deduction + max(0.0, float(other_income_deductions))
    tax_base = max(0.0, earned_income_amount - total_income_deductions)
    calculated_income_tax = max(0.0, comprehensive_income_tax(tax_base))
    earned_credit = earned_income_tax_credit(calculated_income_tax=calculated_income_tax, earned_income_amount=earned_income_amount, comprehensive_income_amount=earned_income_amount, gross_salary=gross_salary)
    standard_credit = 130000 if use_standard_tax_credit else 0.0
    total_tax_credits = earned_credit + standard_credit + max(0.0, float(other_tax_credits))
    income_tax = max(0.0, calculated_income_tax - total_tax_credits)
    local_income_tax = income_tax * TAX_POLICY_2026['local_income_tax_rate']
    total_tax = income_tax + local_income_tax
    return {'gross_salary': gross_salary, 'earned_income_amount': earned_income_amount, 'income_tax': income_tax, 'local_income_tax': local_income_tax, 'total_tax': total_tax}

def pension_incremental_tax_during_existing_job(person_name, age, monthly_pension, income_history, pension_months, dependent_count=0):
    """
    기존 직장 근무 중 국민연금 때문에 추가로 발생하는 세금만 계산.
    66세가 되는 해 말 퇴직이므로 age <= 66 구간을 기존 직장 중복기간으로 본다.
    """
    cfg = EMPLOYMENT_ASSUMPTIONS[person_name]
    if age > cfg['retirement_age']:
        return 0.0
    gross_salary = annual_salary_at_age(current_age=cfg['current_age'], current_monthly_salary=cfg['current_monthly_salary'], annual_wage_growth=cfg['annual_wage_growth'], age=age, months_worked=12)
    combined = calculate_combined_wage_pension_tax(gross_salary=gross_salary, monthly_pension=monthly_pension, income_history=income_history, pension_months=pension_months, dependent_count=dependent_count, other_income_deductions=0, other_tax_credits=0, use_standard_tax_credit=True)
    wage_only = calculate_wage_only_tax(gross_salary=gross_salary, dependent_count=dependent_count, other_income_deductions=0, other_tax_credits=0, use_standard_tax_credit=True)
    return max(0.0, combined['total_tax'] - wage_only['total_tax'])

def pension_flow_dict(normal_monthly_pension, income_history, birth_year, birth_month, claim_age, dependent_count=0, end_age=100, person_name=None):
    """
    pension_to_age_net() 결과를 달력연도 기준 dict로 변환.

    person_name이 "A씨" 또는 "배우자"이면,
    정상연금 개시 후 기존 직장 퇴직(66세가 되는 해 말)까지는
    근로소득+연금 합산과세로 인해 '연금 때문에 추가된 세금'을 반영한다.

    66세 이후에는 연금소득 단독 과세를 적용한다.
    재취업 시나리오는 별도 생애사건 모듈에서 처리한다.

    금액은 2026년 제도·세법 고정 현재가치 기준.
    """
    flow = pension_to_age_net(normal_monthly_pension=normal_monthly_pension, income_history=income_history, birth_year=birth_year, birth_month=birth_month, claim_age=claim_age, dependent_count=dependent_count, end_age=end_age)
    out = {}
    for _, row in flow.iterrows():
        age = int(row['연령'])
        calendar_year = int(birth_year + age)
        months_received = int(row['수령개월'])
        gross_annual = float(row['세전연액(원)'])
        gross_monthly = float(row['세전월액(원)'])
        pension_tax = float(row['세금(원)'])
        tax_method = '연금소득 단독과세'
        if person_name in EMPLOYMENT_ASSUMPTIONS and age <= EMPLOYMENT_ASSUMPTIONS[person_name]['retirement_age'] and (months_received > 0):
            pension_tax = pension_incremental_tax_during_existing_job(person_name=person_name, age=age, monthly_pension=gross_monthly, income_history=income_history, pension_months=months_received, dependent_count=dependent_count)
            tax_method = '근로+연금 합산과세 중 연금 귀속 추가세액'
        net_annual = gross_annual - pension_tax
        net_monthly_equiv = net_annual / months_received if months_received > 0 else 0.0
        prev_cum_gross = list(out.values())[-1]['cumulative_gross'] if out else 0.0
        prev_cum_net = list(out.values())[-1]['cumulative_net'] if out else 0.0
        out[calendar_year] = {'age': age, 'months_received': months_received, 'claim_type': row['수령유형'], 'tax_method': tax_method, 'gross_monthly_pension': gross_monthly, 'gross_annual_pension': gross_annual, 'tax': float(pension_tax), 'net_annual_pension': float(net_annual), 'net_monthly_equivalent': float(net_monthly_equiv), 'cumulative_gross': float(prev_cum_gross + gross_annual), 'cumulative_net': float(prev_cum_net + net_annual)}
    return out
