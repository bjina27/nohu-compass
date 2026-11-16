"""Full simulation 단일 진입함수 (투자모듈·Monte Carlo 연결용).

한 번 호출 = Monte Carlo path 1개.

포함 항목
- 근로소득, 재취업(KLoSA Beta-Binomial), 세금(임시 차감률)
- 국민연금 세후(근로/재취업 결합과세 증분방식), 퇴직급여/IRP(개인별 lump_sum/annuity)
- 생활비, 주택담보대출 상환
- 부모 정기지원, stroke, LTC (만 100세 cutoff)
- 자녀 정기지원, 독립·결혼, 일회성 지원, affordability cap, 증여세(자녀 부담)
- 투자손익 입력: investment_profits / investment_returns / investment_fn 중 하나

재현성
- master_seed 하나에서 재취업·부모·자녀·투자 RNG 스트림을 각각 파생한다(rng_streams.py).
- 재취업 상태는 path마다 한 번만 추첨하고, 국민연금 adapter와 cashflow 엔진이
  같은 reemployment_state를 공유한다(재추첨 없음).

향후 Monte Carlo 예시
    for i in range(n_paths):
        rows = run_full_simulation(master_seed=base_seed + i, investment_fn=my_fn)
"""
from __future__ import annotations

from functools import lru_cache

from calculator_bridge import compute_retirement_net_flows
from config import BASE_CONFIG, HOUSEHOLD
from engine import simulate
from interfaces.housing import build_housing_flows
from nps_net_adapter import build_nps_net_flows
from reemployment_risk import sample_household_reemployment
from scenarios import SCENARIOS
from parent_risk import sample_parent_events
from child_risk import sample_child_events
from event_overrides import (
    apply_child_overrides, apply_parent_overrides, apply_reemployment_overrides,
)

DEFAULT_MASTER_SEED = 20261114

# IRP 연금수령 중 잔액 운용수익률(연, 세전·과세이연) 기본 가정.
# 원리금보장형 운용 가정: 팀 시장가정의 현금 세전 기대수익률 3.32%
# (data/market/market_assumptions_20261031_pre2025.json). 팀 결정으로 변경 가능.
# 일시금 선택에는 영향 없음.
IRP_RETURN_RATE = 0.0332


@lru_cache(maxsize=64)
def _retirement_flows(a_method, spouse_method, a_payout_years, spouse_payout_years,
                      irp_return_rate=IRP_RETURN_RATE):
    result = compute_retirement_net_flows(
        a_method=a_method,
        spouse_method=spouse_method,
        a_payout_years=a_payout_years,
        spouse_payout_years=spouse_payout_years,
        irp_return_rate=irp_return_rate,
    )
    return dict(result.net_annual_nominal)


@lru_cache(maxsize=64)
def _year_end_lump_sums(a_method, spouse_method, a_payout_years, spouse_payout_years):
    """일시금을 고른 사람의 퇴직급여 {연도: 세후 금액}.

    66세 연말 퇴직 시 받는 일시금이므로 그해 운용기간은 0으로 본다
    (investment_return_fn 반년복리 계산에서만 사용). IRP 연금 수령분은 포함하지 않는다.
    """
    result = compute_retirement_net_flows(
        a_method=a_method,
        spouse_method=spouse_method,
        a_payout_years=a_payout_years,
        spouse_payout_years=spouse_payout_years,
    )
    out = {}
    for key, method in result.methods.items():
        if method == "lump_sum":
            for year, amount in result.by_person_net[key].items():
                out[year] = out.get(year, 0) + amount
    return out


@lru_cache(maxsize=8)
def _housing_flows(config):
    return dict(build_housing_flows(config).cashflows)


def run_full_simulation(
    master_seed=DEFAULT_MASTER_SEED,
    scenario=None,
    config=BASE_CONFIG,
    household=HOUSEHOLD,
    a_method="lump_sum",
    spouse_method="lump_sum",
    a_payout_years=20,
    spouse_payout_years=20,
    with_housing=True,
    investment_profits=None,
    investment_returns=None,
    investment_fn=None,
    return_details=False,
    investment_return_fn=None,  # New optional API; old positional calls unchanged.
    spending_policy=None,  # None keeps the original plan-cost ledger.
    claim_ages=None,  # 국민연금 개시 나이 {'a': 60~70, 'spouse': 59~69}. None = 정상수령.
    irp_return_rate=IRP_RETURN_RATE,  # IRP 연금수령 중 잔액 운용수익률 (일시금에는 무관)
    child_overrides=None,         # 자녀 결혼·독립 연도/지원금 지정 (event_overrides.py 참고)
    parent_overrides=None,        # 부모 뇌졸중·장기요양 연도 지정
    reemployment_overrides=None,  # 재취업 기간·월소득 지정
):
    """국민연금·퇴직급여·주택비가 모두 연결된 full cashflow path 1개를 계산한다.

    scenario 기본값은 SCENARIOS["full"] (재취업 + 부모 + 자녀 확률형 이벤트).
    return_details=True이면 (rows, details) 튜플을 반환한다.
    """
    if scenario is None:
        scenario = SCENARIOS["full"]

    # 재취업 상태는 path당 1회만 추첨해 모든 모듈이 공유한다.
    reemployment_state = (
        sample_household_reemployment(random_seed=master_seed)
        if scenario.reemployment else None
    )

    # 사건 직접 지정: 지정하지 않은 사건은 같은 seed의 확률 추첨 결과를 그대로 쓴다.
    parent_event_state = None
    child_event_state = None
    if reemployment_overrides:
        if reemployment_state is None:
            raise ValueError("재취업 지정은 재취업 이벤트가 켜진 시나리오에서만 가능합니다.")
        reemployment_state, scenario = apply_reemployment_overrides(
            reemployment_state, reemployment_overrides, scenario)
    if parent_overrides:
        if not scenario.parent_events:
            raise ValueError("부모 사건 지정은 부모 이벤트가 켜진 시나리오에서만 가능합니다.")
        parent_event_state = apply_parent_overrides(
            sample_parent_events(scenario=scenario, config=config, random_seed=master_seed),
            parent_overrides, config, scenario)
    if child_overrides:
        if not scenario.child_events:
            raise ValueError("자녀 사건 지정은 자녀 이벤트가 켜진 시나리오에서만 가능합니다.")
        child_event_state = apply_child_overrides(
            sample_child_events(scenario=scenario, config=config, random_seed=master_seed),
            child_overrides, config)

    nps = build_nps_net_flows(
        scenario=scenario,
        config=config,
        household=household,
        reemployment_state=reemployment_state,
        claim_ages=claim_ages,
    )
    # lru_cache 결과를 엔진이 변경하지 않도록 사본을 넘긴다.
    retirement_flows = dict(_retirement_flows(
        a_method, spouse_method, a_payout_years, spouse_payout_years, irp_return_rate
    ))
    housing_costs = dict(_housing_flows(config)) if with_housing else None

    rows = simulate(
        scenario=scenario,
        config=config,
        household=household,
        pension_flows=nps.household_net_nominal,
        retirement_flows=retirement_flows,
        housing_costs=housing_costs,
        investment_profits=investment_profits,
        investment_returns=investment_returns,
        investment_fn=investment_fn,
        investment_return_fn=investment_return_fn,
        spending_policy=spending_policy,
        year_end_inflows=dict(_year_end_lump_sums(
            a_method, spouse_method, a_payout_years, spouse_payout_years
        )),
        random_seed=master_seed,
        reemployment_state=reemployment_state,
        parent_event_state=parent_event_state,
        child_event_state=child_event_state,
    )

    if not return_details:
        return rows

    details = {
        "master_seed": master_seed,
        "reemployment_state": reemployment_state,
        "parent_event_state": parent_event_state,
        "child_event_state": child_event_state,
        "nps": nps,
        "retirement_flows": retirement_flows,
        "housing_costs": housing_costs,
        "retirement_methods": {
            "a": (a_method, a_payout_years),
            "spouse": (spouse_method, spouse_payout_years),
        },
    }
    return rows, details
