"""실제 팀원 계산기와 연도별 AFPK 현금흐름 엔진 사이 어댑터.

국민연금 계산 함수는 세전 금액만 산출하므로 기본적으로 엔진에 넘길
세후 pension_flows를 자동 생성하지 않음.
IRP 계산기는 제공된 퇴직소득세(국세) 추정값으로 세후 현금흐름을 생성함.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from calculators.national_pension import nps_calculator
from calculators.retirement_pension import POLICY, PEOPLE, build_irp_pension_schedule
from calculators.irp_with_return import build_irp_schedule_with_return

PERSONS = {
    "a": {"birth_year": 1969, "claim_age": 65, "start_year": 2034, "reference_monthly": 1_030_400},
    "spouse": {"birth_year": 1967, "claim_age": 64, "start_year": 2031, "reference_monthly": 1_710_800},
}
RETIREMENT = {
    "a": {"source_name": "A씨", "year": 2035},
    "spouse": {"source_name": "배우자", "year": 2033},
}


@dataclass(frozen=True)
class NpsResult:
    gross_monthly_2026: dict[str, int]
    gross_annual_nominal: dict[int, int]
    by_person_gross: dict[str, dict[int, int]]
    b_values: dict[str, float]


@dataclass(frozen=True)
class RetirementResult:
    net_annual_nominal: dict[int, int]
    by_person_net: dict[str, dict[int, int]]
    irp_balance_by_person: dict[str, dict[int, int]]
    methods: dict[str, str]


def compute_nps_gross_preview(
    start_year=2026,
    end_year=2069,
    inflation_rate=0.022,
    data_path=None,
):
    """실제 nps_calculator() 실행. 결과는 세전 참고자료(엔진 입력 아님).

    수급개시연도 전체 12개월 수급, 사망 없음, 현역 노령연금 감액 없음 등
    아직 확인되지 않은 가정을 포함한다. 출생월 확인 후 첫해 지급개월수 수정 필요.
    """
    if not -0.99 < inflation_rate <= 0.5 or end_year < start_year:
        raise ValueError("물가상승률 또는 연도 범위가 잘못되었습니다.")
    if data_path is None:
        data_path = Path(__file__).resolve().parent / 'data' / 'nps_income_history.json'
    with Path(data_path).open(encoding='utf-8') as f:
        histories = json.load(f)

    gross_monthly = {}
    b_values = {}
    by_person = {}
    annual_total = {}
    for key, person in PERSONS.items():
        if key not in histories:
            raise ValueError(f"가입소득 이력 누락: {key}")
        result = nps_calculator(
            birth_year=person['birth_year'],
            income_history=histories[key],
            claim_age=person['claim_age'],
        )
        if not result['normal']['eligible']:
            raise ValueError(f"{key}: 국민연금 수급자격 미충족")
        monthly = int(result['claim']['adjusted_monthly_pension'])
        gross_monthly[key] = monthly
        b_values[key] = float(result['normal']['B'])
        # 2026년 가치 기준 월액을 연도별 명목액으로 환산
        schedule = {
            year: round(monthly * 12 * (1 + inflation_rate)**(year-start_year))
            for year in range(max(start_year, person['start_year']), end_year+1)
        }
        by_person[key] = schedule
        for year, amount in schedule.items():
            annual_total[year] = annual_total.get(year, 0) + amount
    return NpsResult(gross_monthly, annual_total, by_person, b_values)


def _validate_schedule(schedule, label):
    if not isinstance(schedule, Mapping):
        raise TypeError(f"{label}: {{연도: 정수 원화}} 구조를 사용하세요")
    for year, amount in schedule.items():
        if not isinstance(year, int) or isinstance(year, bool):
            raise TypeError(f"{label}: 연도가 정수가 아닙니다")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError(f"{label}: 금액은 0 이상의 정수 원화여야 합니다")


def net_pension_flows_from_verified_schedules(by_person_net, end_year=2069):
    """확인된 *세후*·재직중 감액 반영 명목 연금 스케줄만 엔진에 연결.

    by_person_net = {
        'a': {2034: amount, ...},
        'spouse': {2031: amount, ...},
    }
    지정하지 않은 연도는 엔진에서 0원으로 처리되므로 실수 방지를 위해
    개인별 수급기간 모든 연도의 키를 요구한다.
    """
    if set(by_person_net) != set(PERSONS):
        raise ValueError("세후 국민연금 일정은 A씨와 배우자 모두 필요합니다")
    combined = {}
    for key, spec in PERSONS.items():
        schedule = by_person_net[key]
        _validate_schedule(schedule, key)
        required_years = set(range(spec['start_year'], end_year + 1))
        missing = required_years - set(schedule)
        if missing:
            raise ValueError(f"{key}: 세후 국민연금 연도 누락: {min(missing)}")
        if any(year < spec['start_year'] for year in schedule):
            raise ValueError(f"{key}: 수급개시 이전 연금액 존재")
        for year, amount in schedule.items():
            if year <= end_year:
                combined[year] = combined.get(year, 0) + amount
    return combined


def compute_retirement_net_flows(
    a_method='lump_sum',
    spouse_method='lump_sum',
    a_payout_years=20,
    spouse_payout_years=20,
    irp_return_rate=0.0,
):
    """실제 build_irp_pension_schedule() 호출 및 일시금과 연금 택일.

    irp_return_rate: IRP 연금수령 중 잔액 운용수익률(연, 세전·과세이연).
        0.0이면 팀원 원본 스케줄과 동일. 0이 아니면 calculators/irp_with_return.py 사용.
    """
    methods = {'a': a_method, 'spouse': spouse_method}
    years = {'a': a_payout_years, 'spouse': spouse_payout_years}
    annual_total = {}
    by_person = {}
    balances = {}
    for key, method in methods.items():
        if method not in ('lump_sum','annuity'):
            raise ValueError(f"{key}: 잘못된 퇴직급여 수령방식: {method}")
        p = PEOPLE[RETIREMENT[key]['source_name']]
        retirement_year = RETIREMENT[key]['year']
        gross = int(p['gross_retirement_benefit'])
        national_tax = int(p['lump_sum_national_tax'])
        by_person[key] = {}
        balances[key] = {}
        if method == 'lump_sum':
            # 팀원이 입력한 추정 퇴직소득세(국세) + 지방소득세 10%.
            # 세액 자체는 검증되지 않은 팀원 입력값이다.
            local_tax = round(national_tax * POLICY['local_income_tax_rate'])
            net = gross - national_tax - local_tax
            if net < 0:
                raise ValueError(f"{key}: 퇴직급여 세후 금액 음수")
            by_person[key][retirement_year] = net
        else:
            if years[key] <= 0:
                raise ValueError(f"{key}: 지급기간은 1 이상")
            expected_first_year = 2026 + p['pension_start_age'] - p['current_age']
            if expected_first_year != retirement_year:
                raise ValueError(f"{key}: IRP 수령 시작연도와 퇴직연도 불일치")
            # 66세 연말 퇴직 → IRP 연금 첫 수령은 퇴직 다음 해(67세)부터.
            # (팀 결정 2026-11-16. 이전에는 퇴직한 해부터 수령)
            first_payment_year = retirement_year + 1
            schedule, summary = build_irp_schedule_with_return(
                gross_retirement_benefit=gross,
                lump_sum_national_tax=national_tax,
                pension_start_age=p['pension_start_age'] + 1,
                payout_years=years[key],
                annual_return=irp_return_rate,
            )
            for _, row in schedule.iterrows():
                year = first_payment_year + int(row['수령연차']) - 1
                by_person[key][year] = int(row['세후수령액'])
                balances[key][year] = int(row['기말 IRP잔액'])
        for year, amount in by_person[key].items():
            annual_total[year] = annual_total.get(year,0) + amount
    return RetirementResult(annual_total, by_person, balances, methods)
