"""팀원 국민연금 계산기 -> AFPK engine.py 연결 어댑터.

핵심 규약
- 팀원 계산기는 2026년 실질가치/2026년 세법 고정 추정치.
- 기본 엔진은 해당 연도 명목원화 세후 유입액을 받는다.
- 기존 직장/재취업 소득은 engine.py가 실제 산출한 금액만 사용한다.
- 연금이 있는 연도의 추가 종합소득세만 연금에서 차감하여
  엔진의 별도 근로소득 차감액과 중복되지 않게 한다.
- 재직자 노령연금 감액 기준 초과 시 모델에 없는 감액을 조용히 생략하지 않고 오류를 낸다.
- 건강보험료, 연금 외 추가 소득, 사망률, 향후 법령변경은 미반영이다.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from calculators import national_pension as nps
from config import A, SPOUSE, BASE_CONFIG
from engine import calculate_regular_wage, calculate_reemployment_wage, inflation_factor
from scenarios import ScenarioConfig

DATA_PATH = Path(__file__).resolve().parent / 'data' / 'nps_income_history.json'

# 팀원이 정한 가정: 두 사람 모두 6월생, 본인 외 기본공제 대상자 없음.
# 필요하면 build_nps_net_flows() 인자로 변경.
DEFAULT_BIRTH_MONTHS = {'a': 6, 'spouse': 6}
DEFAULT_DEPENDENT_COUNTS = {'a': 0, 'spouse': 0}

@dataclass(frozen=True)
class NpsNetFlows:
    household_net_nominal: dict[int, int]
    by_person_net_nominal: dict[str, dict[int, int]]
    by_person_gross_nominal: dict[str, dict[int, int]]
    gross_monthly_2026: dict[str, int]
    b_values: dict[str, float]
    details: list[dict]
    status: str = '2026 제도·세법 고정 세후 추정 / 재직자 감액·건강보험 미반영'
    # 사람별 수령시기 정보: claim_age, claim_year, claim_type(조기/정상/연기), adjustment_rate,
    # normal_monthly_2026(정상수령 기준 월액)
    claim_info: dict = field(default_factory=dict)


def _person_key(person):
    """전달된 페르소나 객체를 사용할 때 이름 대신 key 우선."""
    if getattr(person, 'key', None) in ('a', 'spouse'):
        return person.key
    if person.name == 'A씨':
        return 'a'
    if person.name == '배우자':
        return 'spouse'
    raise ValueError(f'등록되지 않은 사람: {person!r}')


def build_nps_net_flows(
    scenario=None,
    config=BASE_CONFIG,
    household=(A, SPOUSE),
    birth_months=None,
    dependent_counts=None,
    data_path=None,
    reemployment_state=None,
    claim_ages=None,
):
    """시나리오별 연도→세후 명목 연금액 딕셔너리를 생성한다.

    출생월 6월 -> 수급개시연도 7~12월, 6개월 지급.
    정상 연금 개시연도 A씨 2034 / 배우자 2031.
    2026년 기준 재직자 감액 문턱을 초과하면 구현되지 않은 감액을 경고하도록 예외.

    claim_ages: {'a': 나이, 'spouse': 나이} — 국민연금 수령 개시 나이(만 나이, 해당 연도 생일 다음 달부터).
        생략한 사람·None이면 정상 개시연령. 범위: 정상연령-5(조기) ~ 정상연령+5(연기).
        - 조기: 월 0.5% 감액(계산기 apply_claim_timing). 조기수령 시작~정상연령 전까지
          근로·재취업 소득월액(근로소득공제 후, 2026년 가치)이 A값을 넘는 해가 있으면
          '소득 있는 업무 종사'로 조기노령연금 대상이 아니므로 ValueError.
        - 연기: 월 0.6% 가산. 부분연기(50~90%)는 지원하지 않음.
    """
    if scenario is None:
        scenario = ScenarioConfig()
    birth_months = dict(DEFAULT_BIRTH_MONTHS if birth_months is None else birth_months)
    dependent_counts = dict(DEFAULT_DEPENDENT_COUNTS if dependent_counts is None else dependent_counts)
    data_path = DATA_PATH if data_path is None else Path(data_path)
    with data_path.open(encoding='utf-8') as file:
        histories = json.load(file)

    actual_people = {_person_key(p): p for p in household}
    if set(actual_people) != {'a','spouse'}:
        raise ValueError('가구 구성은 A씨, 배우자 두 명이어야 합니다.')

    total_net = {}
    by_net = {}
    by_gross = {}
    monthly_gross = {}
    b_values = {}
    details = []

    claim_ages = dict(claim_ages or {})
    if set(claim_ages) - {'a', 'spouse'}:
        raise ValueError("claim_ages의 키는 'a', 'spouse'만 가능합니다.")
    claim_info = {}

    for key, person in actual_people.items():
        history = histories[key]
        normal_age = nps.normal_pension_age(person.birth_year)
        claim_age = claim_ages.get(key)
        if claim_age is None:
            claim_age = normal_age
        if not isinstance(claim_age, int) or isinstance(claim_age, bool):
            raise TypeError(f'{key}: 국민연금 개시 나이는 정수여야 합니다.')
        if not nps.earliest_early_age(person.birth_year) <= claim_age <= normal_age + 5:
            raise ValueError(
                f'{key}: 국민연금 개시 나이 {claim_age}세는 허용 범위'
                f'({normal_age - 5}~{normal_age + 5}세) 밖입니다.'
            )
        normal = nps.nps_calculator(
            birth_year=person.birth_year, income_history=history, claim_age=claim_age
        )
        if not normal['normal']['eligible']:
            raise ValueError(f'{key}: 국민연금 수급 요건 미충족')
        month_2026 = int(normal['claim']['adjusted_monthly_pension'])
        claim_year = person.birth_year + claim_age

        # 조기수령 소득요건: 조기 개시~정상연령 전까지 소득월액이 A값 이하여야 한다.
        if claim_age < normal_age:
            for year in range(claim_year, person.birth_year + normal_age):
                wage_nominal = (
                    calculate_regular_wage(person, year, config)
                    + calculate_reemployment_wage(
                        person, year, config, scenario, reemployment_state
                    )
                )
                wage_2026 = wage_nominal / inflation_factor(year, config)
                monthly_income_amount = max(
                    0.0, wage_2026 - nps.earned_income_deduction(wage_2026)
                ) / 12
                check = nps.apply_claim_timing(
                    normal_monthly_pension=normal['normal']['normal_monthly_pension'],
                    birth_year=person.birth_year, claim_age=claim_age,
                    monthly_income_amount=monthly_income_amount,
                )
                if not check['early_income_ok']:
                    raise ValueError(
                        f'{key} {year}: 조기수령 기간 중 소득월액 {monthly_income_amount:,.0f}원'
                        f'(2026년 가치)이 A값 {nps.POLICY_2026["a_value"]:,}원을 넘어 '
                        f'조기노령연금을 받을 수 없습니다.'
                    )

        claim_info[key] = {
            'claim_age': claim_age,
            'claim_year': claim_year,
            'claim_type': normal['claim']['claim_type'],
            'adjustment_rate': normal['claim']['adjustment_rate'],
            'normal_monthly_2026': int(normal['claim']['normal_monthly_pension']),
        }
        first_months = nps.first_year_payment_months(birth_months[key])
        dependents = dependent_counts[key]
        if not isinstance(dependents, int) or isinstance(dependents, bool) or dependents < 0:
            raise ValueError('부양가족 공제 인원은 0 이상의 정수여야 합니다.')
        monthly_gross[key] = month_2026
        b_values[key] = float(normal['normal']['B'])
        by_net[key] = {}
        by_gross[key] = {}

        for year in range(max(claim_year, config.start_year), config.end_year + 1):
            age = year - person.birth_year
            months = first_months if year == claim_year else 12
            factor = inflation_factor(year, config)
            gross_2026 = month_2026 * months

            # 반드시 엔진의 근로소득만 사용. 팀원 계산기의 별도 임금경로는 사용하지 않음.
            gross_wage_nominal = (
                calculate_regular_wage(person, year, config)
                + calculate_reemployment_wage(
                    person, year, config, scenario, reemployment_state
                )
            )
            # 2026년 고정 세법을 적용하기 위해 연금·급여 모두 2026년 가치로 변환.
            gross_wage_2026 = gross_wage_nominal / factor
            if months == 0:
                tax_2026 = 0.0
                method = '첫 수급연도 지급 없음'
            elif gross_wage_nominal > 0:
                # 2026년 소득활동 노령연금 감액 문턱: A값+200만원.
                # 기본 페르소나 소득은 문턱 아래로 예상되지만 초과하면
                # 조용히 감액 0으로 처리하지 않고 감액 전용 모델을 요구한다.
                earned_amount_2026 = max(
                    0.0,
                    gross_wage_2026 - nps.earned_income_deduction(gross_wage_2026),
                )
                cutoff = nps.POLICY_2026['a_value'] + 2_000_000
                if age < normal_age + 5 and earned_amount_2026 / 12 >= cutoff:
                    raise NotImplementedError(
                        f'{key} {year}: 2026년 기준 노령연금 재직자 감액 대상. '
                        '재직자 감액 모듈이 필요합니다.'
                    )
                combined = nps.calculate_combined_wage_pension_tax(
                    gross_salary=gross_wage_2026,
                    monthly_pension=month_2026,
                    income_history=history,
                    pension_months=months,
                    dependent_count=dependents,
                )
                wage_only = nps.calculate_wage_only_tax(
                    gross_salary=gross_wage_2026,
                    dependent_count=dependents,
                )
                tax_2026 = max(0.0, combined['total_tax'] - wage_only['total_tax'])
                method = '근로+연금 합산과세(연금 귀속 증분세액)'
            else:
                only = nps.calculate_after_tax_nps(
                    monthly_pension=month_2026,
                    income_history=history,
                    dependent_count=dependents,
                    months_received=months,
                )
                tax_2026 = float(only['total_tax'])
                method = '연금소득만 과세'

            net_2026 = gross_2026 - tax_2026
            if net_2026 < 0:
                raise ValueError(f'{key} {year}: 연금보다 세금이 큽니다')
            gross_nominal = round(gross_2026 * factor)
            tax_nominal = round(tax_2026 * factor)
            net_nominal = gross_nominal - tax_nominal
            by_net[key][year] = net_nominal
            by_gross[key][year] = gross_nominal
            total_net[year] = total_net.get(year, 0) + net_nominal
            details.append({
                'scenario': scenario.name,
                'person': key,
                'year': year,
                'age': age,
                'months_received': months,
                'gross_wage_nominal': gross_wage_nominal,
                'gross_pension_nominal': gross_nominal,
                'incremental_pension_tax_nominal': tax_nominal,
                'net_pension_nominal': net_nominal,
                'tax_method': method,
                'claim_age': claim_age,
                'claim_type': normal['claim']['claim_type'],
            })

    return NpsNetFlows(total_net, by_net, by_gross, monthly_gross, b_values, details,
                       claim_info=claim_info)
