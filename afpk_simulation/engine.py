
from collections.abc import Mapping
import math

from config import (
    A,
    SPOUSE,
    HOUSEHOLD,
    BASE_CONFIG,
)
from scenarios import ScenarioConfig
from reemployment_risk import sample_household_reemployment
from parent_risk import sample_parent_events
from child_risk import sample_child_events
from gift_tax import estimate_child_gift_tax
from rng_streams import derive_rng, validate_seed
from simulation.spending_policy import (
    validate_spending_policy, apply_spending_policy,
    discretionary_child_one_time_allowed,
)


def get_age(person, year):
    """출생연도 기준 단순 연령."""
    return year - person.birth_year


def inflation_factor(year, config):
    """2026년 대비 물가상승 배율."""
    return (
        1 + config.inflation_rate
    ) ** (year - config.start_year)


def validate_inputs(
    config=BASE_CONFIG,
    household=HOUSEHOLD,
    scenario=None,
):
    """잘못된 입력값을 계산 전에 차단한다."""

    # v1은 2026년 금융자산과 임금을 기준으로 시작
    if config.start_year != 2026:
        raise ValueError(
            "v1 엔진의 시작연도는 2026년이어야 합니다."
        )

    if config.end_year < config.start_year:
        raise ValueError(
            "종료연도는 시작연도보다 빠를 수 없습니다."
        )

    if not -0.99 < config.inflation_rate <= 0.5:
        raise ValueError(
            "물가상승률은 소수로 입력하세요. "
            "예: 2.2%는 0.022"
        )

    nonnegative_fields = (
        "initial_financial_assets",
        "base_gross_income",
        "base_tax_and_insurance",
        "monthly_living_cost",
        "monthly_son_support",
        "annual_a_mother_support",
        "annual_spouse_mother_support",
    )

    for field in nonnegative_fields:
        if getattr(config, field) < 0:
            raise ValueError(
                f"{field}에는 음수를 입력할 수 없습니다."
            )

    # 생활비 변경: 시작연도와 변경 후 금액은 함께 지정하거나 함께 생략한다.
    change_year = getattr(config, "living_cost_change_year", None)
    change_amount = getattr(config, "monthly_living_cost_after_change", None)
    if (change_year is None) != (change_amount is None):
        raise ValueError(
            "living_cost_change_year와 monthly_living_cost_after_change는 함께 지정해야 합니다."
        )
    if change_year is not None:
        if isinstance(change_year, bool) or not isinstance(change_year, int):
            raise ValueError("living_cost_change_year는 정수 연도여야 합니다.")
        if not config.start_year <= change_year <= config.end_year:
            raise ValueError(
                f"living_cost_change_year는 {config.start_year}~{config.end_year} 사이여야 합니다."
            )
        if isinstance(change_amount, bool) or not isinstance(change_amount, int) or change_amount < 0:
            raise ValueError("monthly_living_cost_after_change는 0 이상의 정수 원화여야 합니다.")

    support_end_fields = (
        "son_support_end_year",
        "a_mother_support_end_year",
        "spouse_mother_support_end_year",
    )

    for field in support_end_fields:
        value = getattr(config, field)

        if value is not None and not isinstance(value, int):
            raise ValueError(
                f"{field}는 연도 또는 None이어야 합니다."
            )

    keys = [person.key for person in household]

    if len(keys) != len(set(keys)):
        raise ValueError("Person.key가 중복되었습니다.")

    if set(keys) != {"a", "spouse"}:
        raise ValueError(
            "현재 v1은 key가 'a', 'spouse'인 "
            "두 사람을 대상으로 합니다."
        )

    for person in household:
        if person.annual_wage_2026 < 0:
            raise ValueError(
                f"{person.name}: 근로소득은 음수일 수 없습니다."
            )

        if not -0.99 < person.wage_growth_rate <= 0.5:
            raise ValueError(
                f"{person.name}: 임금상승률을 확인하세요. "
                "3.08%는 0.0308로 입력합니다."
            )

        if not (
            0 <= person.deduction_2026
            <= person.annual_wage_2026
        ):
            raise ValueError(
                f"{person.name}: 2026년 차감액이 잘못되었습니다."
            )

        if not 0 <= person.deduction_rate_60plus <= 1:
            raise ValueError(
                f"{person.name}: 60세 이후 차감률이 잘못되었습니다."
            )

        if not 0 < person.retirement_age <= 100:
            raise ValueError(
                f"{person.name}: 퇴직연령이 잘못되었습니다."
            )

    if scenario is not None:
        if scenario.reemployment:
            if (
                scenario.a_reemployment_monthly < 0
                or scenario.spouse_reemployment_monthly < 0
            ):
                raise ValueError(
                    "재취업 월급은 음수일 수 없습니다."
                )

        if scenario.parent_events:
            probabilities = (
                scenario.a_mother_stroke_annual_probability,
                scenario.spouse_mother_ltc_probability_83_84,
                scenario.spouse_mother_ltc_probability_85plus,
            )
            if any(not 0 <= p <= 1 for p in probabilities):
                raise ValueError(
                    "노부모 사건확률은 0~1 사이여야 합니다."
                )
            if scenario.parent_mother_age_2026 < 0:
                raise ValueError(
                    "노부모 연령은 음수일 수 없습니다."
                )
            if (
                scenario.a_mother_stroke_cost_2026 < 0
                or scenario.spouse_mother_ltc_annual_cost_2026 < 0
            ):
                raise ValueError(
                    "노부모 추가비용은 음수일 수 없습니다."
                )

        if scenario.child_events:
            child_probabilities = (
                scenario.son_independence_probability_27_29,
                scenario.son_independence_probability_30_34,
                scenario.son_marriage_probability_27_29,
                scenario.son_marriage_probability_30_34,
                scenario.son_independence_probability_35_39,
                scenario.son_independence_probability_40_44,
                scenario.son_marriage_probability_35_39,
                scenario.son_marriage_probability_40_44,
                scenario.son_independence_support_probability,
            )
            if any(not 0 <= p <= 1 for p in child_probabilities):
                raise ValueError(
                    "자녀 생애이벤트 확률은 0~1 사이여야 합니다."
                )
            bracket_total = sum(
                item["probability"]
                for item in scenario.son_marriage_support_brackets_2015
            )
            if abs(bracket_total - 1.0) > 1e-9:
                raise ValueError(
                    "결혼지원금 구간 확률의 합은 1이어야 합니다."
                )
            if any(
                item["representative_amount"] < 0
                for item in scenario.son_marriage_support_brackets_2015
            ):
                raise ValueError(
                    "결혼지원 대표금액은 음수일 수 없습니다."
                )
            if scenario.son_independence_support_amount_2024 < 0:
                raise ValueError(
                    "독립지원금은 음수일 수 없습니다."
                )
            if not 0 <= scenario.son_support_months_in_exit_year <= 12:
                raise ValueError(
                    "독립/결혼 발생연도 자녀지원 개월 수는 0~12여야 합니다."
                )
            if config.son_age_2026 != 27:
                raise ValueError(
                    "현재 자녀 이벤트 모형은 2026년 만 27세 페르소나에 맞춰져 있습니다."
                )


def check_persona_2026(
    config=BASE_CONFIG,
    household=HOUSEHOLD,
):
    """2026년 페르소나 입력값 정합성 검증."""

    gross = sum(
        person.annual_wage_2026
        for person in household
    )

    deductions = sum(
        person.deduction_2026
        for person in household
    )

    if gross != config.base_gross_income:
        raise ValueError(
            "2026년 개인별 근로소득 합계와 "
            "가구 세전소득이 일치하지 않습니다."
        )

    if deductions != config.base_tax_and_insurance:
        raise ValueError(
            "2026년 개인별 차감액 합계와 "
            "가구 세금·보험료가 일치하지 않습니다."
        )

    return True


def calculate_regular_wage(person, year, config):
    """66세가 되는 해 말까지 기존 직장에서 받는 세전 근로소득."""

    age = get_age(person, year)

    # retirement_age=66은 "66세 연말 퇴직"을 의미한다.
    # 따라서 66세 연도 급여는 12개월 반영하고 67세부터 0원이다.
    if age > person.retirement_age:
        return 0

    years = year - config.start_year

    return round(
        person.annual_wage_2026
        * (1 + person.wage_growth_rate) ** years
    )


def calculate_reemployment_wage(
    person,
    year,
    config,
    scenario,
    reemployment_state=None,
):
    """KLoSA 확률형 재취업 이벤트가 발생한 경우의 세전 근로소득.

    - 66세 연말까지 기존 직장 유지 -> 67세부터 재취업 가능
    - 재취업 발생/지속기간은 reemployment_risk.py에서 한 경로당 한 번 추출
    - 월소득은 2026년 구매력 기준 대표값을 사용하고 별도 임금상승률 가정 없이
      해당 연도의 물가만 반영하여 명목금액으로 변환
    """

    if not scenario.reemployment:
        return 0

    if reemployment_state is None:
        raise ValueError(
            "재취업 이벤트가 켜져 있으면 확률형 재취업 상태가 필요합니다."
        )

    person_state = reemployment_state[person.key]
    if not person_state["success"]:
        return 0

    age = get_age(person, year)
    start_age = person.retirement_age + 1
    duration_years = person_state["duration_years"]
    end_age = start_age + duration_years

    if not start_age <= age < end_age:
        return 0

    monthly_wages = {
        "a": scenario.a_reemployment_monthly,
        "spouse": scenario.spouse_reemployment_monthly,
    }
    if person.key not in monthly_wages:
        raise ValueError(f"정의되지 않은 사람 key: {person.key}")

    # 대표 월소득을 2026년 실질가치로 두고 해당 연도 물가만 반영한다.
    return round(
        monthly_wages[person.key]
        * 12
        * inflation_factor(year, config)
    )


def deduction_rate(person, year):
    """
    사람별 임시 세금·사회보험료 차감률.

    60세 미만:
        2026년 개인별 실효 차감률 사용

    60세 이상:
        국민연금 의무가입 종료를 고려한
        별도 임시 추정률 사용

    주의:
        실제 누진세, 건강보험료 변화 등을
        완전히 계산하는 세금 모듈은 아님.
        [KNOWN LIMITATION] 이번 버전에서는 baseline cashflow와 회귀테스트 보존을 위해
        공식 세법·보험료 산식으로 교체하지 않는다(VALIDATION_REPORT.md 목록 참조).
    """

    age = get_age(person, year)

    if age < person.nps_contribution_end_age:
        if person.annual_wage_2026 == 0:
            return 0.0

        return (
            person.deduction_2026
            / person.annual_wage_2026
        )

    return person.deduction_rate_60plus


def calculate_tax(person, gross_wage, year):
    """개인별 세금·사회보험료 임시 추정."""

    if gross_wage <= 0:
        return 0

    return round(
        gross_wage * deduction_rate(person, year)
    )


def _support_active(year, end_year):
    """
    수동 종료연도가 None이면 계속 지급.
    (자녀 45세·부모 100세 cutoff는 별도 함수에서 적용된다.)
    """
    return end_year is None or year <= end_year


def parent_age(year, config, scenario=None):
    """두 어머니 공통 연령(scenario.parent_mother_age_2026 기준)."""
    if scenario is None:
        scenario = ScenarioConfig()
    return scenario.parent_mother_age_2026 + (year - config.start_year)


def son_age(year, config):
    return config.son_age_2026 + (year - config.start_year)


def parent_cashflow_active(year, config, scenario=None):
    """부모 만 100세 deterministic cutoff.

    만 99세까지 True, 만 100세부터 False.
    사망을 직접 모델링하는 것이 아니라 장기 시뮬레이션용 단순화 규칙이다.
    """
    if scenario is None:
        scenario = ScenarioConfig()
    return parent_age(year, config, scenario) < scenario.parent_cashflow_end_age


def monthly_living_cost_for_year(year, config):
    """해당 연도의 월 생활비(2026년 가치).

    config.living_cost_change_year가 있으면 그 해부터 monthly_living_cost_after_change를 쓴다.
    """
    change_year = getattr(config, "living_cost_change_year", None)
    if change_year is not None and year >= change_year:
        return config.monthly_living_cost_after_change
    return config.monthly_living_cost


def calculate_expenses(year, config, son_support_months=12, scenario=None):
    """부부 생활비 및 가족지원비.

    자녀 독립·결혼 이벤트가 켜진 경우 독립/결혼 발생연도는
    평균적으로 연중 중간에 발생한다고 보고 6개월분만 지급한다.

    deterministic cutoff
    - 부모 만 100세부터 양가 어머니 정기지원 0원
    - 자녀 정기지원 개월 수는 호출부(_son_support_months_for_year)에서
      만 45세 cutoff를 반영해 전달한다.
    """

    if not 0 <= son_support_months <= 12:
        raise ValueError("자녀지원 개월 수는 0~12여야 합니다.")

    factor = inflation_factor(year, config)
    parents_active = parent_cashflow_active(year, config, scenario)

    living = round(
        monthly_living_cost_for_year(year, config) * 12 * factor
    )

    son = (
        round(config.monthly_son_support * son_support_months * factor)
        if _support_active(
            year,
            config.son_support_end_year,
        )
        else 0
    )

    a_mother = (
        round(config.annual_a_mother_support * factor)
        if parents_active and _support_active(
            year,
            config.a_mother_support_end_year,
        )
        else 0
    )

    spouse_mother = (
        round(
            config.annual_spouse_mother_support * factor
        )
        if parents_active and _support_active(
            year,
            config.spouse_mother_support_end_year,
        )
        else 0
    )

    family_support = (
        son + a_mother + spouse_mother
    )

    return {
        "living": living,
        "son": son,
        "a_mother": a_mother,
        "spouse_mother": spouse_mother,
        "family_support": family_support,
        "total": living + family_support,
    }


def calculate_parent_event_costs(
    year,
    config,
    scenario,
    parent_event_state=None,
):
    """노부모 확률형 생애이벤트의 연도별 추가 지출.

    A씨 어머니
    - 83세 이후 최초 뇌졸중 발생연도에만 1회성 비용.

    배우자 어머니
    - 최초 장기요양 인정연도부터 매년 비용이 지속.

    두 비용 모두 2026년 구매력 기준 입력값에 해당 연도 물가만 반영한다.
    """
    if not scenario.parent_events:
        return {
            "a_mother_stroke_cost": 0,
            "spouse_mother_ltc_cost": 0,
            "total": 0,
        }

    if parent_event_state is None:
        raise ValueError(
            "노부모 생애이벤트가 켜져 있으면 확률형 부모 이벤트 상태가 필요합니다."
        )

    stroke_year = parent_event_state["a_mother_stroke_year"]
    ltc_year = parent_event_state["spouse_mother_ltc_entry_year"]

    # 부모 만 100세부터 사건비용 0 (과거 event history는 state에 그대로 유지)
    active = parent_cashflow_active(year, config, scenario)

    a_stroke = 0
    if active and stroke_year is not None and year == stroke_year:
        a_stroke = round(
            scenario.a_mother_stroke_cost_2026
            * inflation_factor(year, config)
        )

    spouse_ltc = 0
    if active and ltc_year is not None and year >= ltc_year:
        spouse_ltc = round(
            scenario.spouse_mother_ltc_annual_cost_2026
            * inflation_factor(year, config)
        )

    return {
        "a_mother_stroke_cost": a_stroke,
        "spouse_mother_ltc_cost": spouse_ltc,
        "total": a_stroke + spouse_ltc,
    }


def _son_support_months_for_year(year, scenario, child_event_state, config=BASE_CONFIG):
    """자녀 정기지원 개월 수.

    독립/결혼 이전 12개월, 최초 독립/결혼 연도 6개월,
    이후 0개월. 자녀 이벤트 OFF이면 기존 12개월 구조를 유지한다.
    자녀가 만 45세가 되는 해부터는 동거 여부와 무관하게 0개월
    (deterministic cutoff, 모든 시나리오 공통).
    """
    if son_age(year, config) >= scenario.son_regular_support_end_age:
        return 0
    if not scenario.child_events:
        return 12
    if child_event_state is None:
        raise ValueError(
            "자녀 생애이벤트가 켜져 있으면 확률형 자녀 이벤트 상태가 필요합니다."
        )
    exit_year = child_event_state.get("first_exit_year")
    if exit_year is None or year < exit_year:
        return 12
    if year == exit_year:
        return scenario.son_support_months_in_exit_year
    return 0


def _independence_support_2026(config, scenario):
    """2024년 독립 주거지원액을 엔진 물가가정으로 2026년 가치로 변환."""
    years = config.start_year - 2024
    return round(
        scenario.son_independence_support_amount_2024
        * (1 + config.inflation_rate) ** years
    )


def _marriage_support_2026(amount_2015, config, scenario):
    """2015년 가격 결혼지원 대표금액을 합의된 CPI 연결 방식으로 2026 가치화."""
    if amount_2015 <= 0:
        return 0
    to_2025 = (
        scenario.marriage_support_cpi_2025
        / scenario.marriage_support_cpi_2015
    )
    # 2025 -> 2026은 계산엔진의 2.2% 물가가정으로 연결.
    return round(
        amount_2015
        * to_2025
        * (1 + config.inflation_rate)
    )


def _child_event_target_support(year, config, scenario, child_event_state):
    """해당 연도의 통계 기반 목표 지원액(지급능력 상한 적용 전)."""
    if not scenario.child_events or child_event_state is None:
        return {
            "event_type": None,
            "target_support_nominal": 0,
            "support_label": None,
            "marriage_event": False,
        }

    independence_year = child_event_state.get("independence_year")
    marriage_year = child_event_state.get("marriage_year")

    # 사용자 지정 지원금(AI 상담 등): 통계 분포 대신 해당 연도 명목 금액을 목표로 쓴다.
    # 지급능력 상한·증여세는 이후 단계에서 그대로 적용된다.
    ind_override = child_event_state.get("independence_support_override_nominal")
    mar_override = child_event_state.get("marriage_support_override_nominal")
    if year == independence_year and ind_override is not None:
        return {
            "event_type": "simple_independence",
            "target_support_nominal": int(ind_override),
            "support_label": "user_specified",
            "marriage_event": False,
        }
    if year == marriage_year and mar_override is not None:
        return {
            "event_type": "marriage",
            "target_support_nominal": int(mar_override),
            "support_label": "user_specified",
            "marriage_event": True,
        }

    # 비혼 단순독립 지원은 독립 발생연도에만 1회.
    if year == independence_year:
        target_2026 = (
            _independence_support_2026(config, scenario)
            if child_event_state.get("independence_support_selected")
            else 0
        )
        return {
            "event_type": "simple_independence",
            "target_support_nominal": round(
                target_2026 * inflation_factor(year, config)
            ),
            "support_label": (
                "independence_housing_support"
                if target_2026 > 0 else "independence_no_parent_support"
            ),
            "marriage_event": False,
        }

    # 결혼지원은 동거->결혼, 독립 후 결혼 모두 동일 분포를 사용.
    if year == marriage_year:
        bracket = child_event_state.get("marriage_support_bracket") or {
            "label": "none", "representative_amount": 0
        }
        target_2026 = _marriage_support_2026(
            int(bracket["representative_amount"]),
            config,
            scenario,
        )
        return {
            "event_type": "marriage",
            "target_support_nominal": round(
                target_2026 * inflation_factor(year, config)
            ),
            "support_label": bracket.get("label"),
            "marriage_event": True,
        }

    return {
        "event_type": None,
        "target_support_nominal": 0,
        "support_label": None,
        "marriage_event": False,
    }


def _next_year_essential_reserve(
    year,
    config,
    scenario,
    parent_event_state,
    housing_costs,
):
    """자녀 선택지원 전에 남겨둘 다음 1년 필수지출 준비금.

    포함
    - 부부 생활비
    - 양가 부모 정기지원
    - 이미 진입한 배우자 어머니 장기요양 지속비
    - 연결된 주택 모듈의 다음 연도 상환액

    미포함
    - 미래 미발생 확률사건(A씨 어머니 뇌졸중 등)
    - 자녀 정기지원(독립/결혼 이벤트가 발생한 뒤이므로 다음 해 0원)
    """
    next_year = year + 1
    if next_year > config.end_year:
        return 0

    factor = inflation_factor(next_year, config)
    living = round(monthly_living_cost_for_year(next_year, config) * 12 * factor)
    # 다음 해 부모가 만 100세 이상이면 정기지원·LTC reserve 0
    parents_active_next = parent_cashflow_active(next_year, config, scenario)
    a_mother = (
        round(config.annual_a_mother_support * factor)
        if parents_active_next
        and _support_active(next_year, config.a_mother_support_end_year)
        else 0
    )
    spouse_mother = (
        round(config.annual_spouse_mother_support * factor)
        if parents_active_next
        and _support_active(next_year, config.spouse_mother_support_end_year)
        else 0
    )

    ongoing_ltc = 0
    if (
        parents_active_next
        and scenario.parent_events
        and parent_event_state is not None
    ):
        ltc_year = parent_event_state.get("spouse_mother_ltc_entry_year")
        if ltc_year is not None and next_year >= ltc_year:
            ongoing_ltc = round(
                scenario.spouse_mother_ltc_annual_cost_2026 * factor
            )

    housing = (
        housing_costs.get(next_year, 0)
        if housing_costs is not None else 0
    )

    return living + a_mother + spouse_mother + ongoing_ltc + housing


def _validate_guardrails(guardrails, config):
    """동적 가드레일 옵션 검증. None이면 None(꺼짐)."""
    if guardrails is None:
        return None
    g = dict(guardrails)
    allowed = {"bridge_reserve_until", "living_floor_monthly_2026",
               "living_cut_years", "living_restore_years"}
    unknown = set(g) - allowed
    if unknown:
        raise ValueError(f"알 수 없는 가드레일 옵션: {sorted(unknown)}")
    until = g.get("bridge_reserve_until")
    if until is not None and (isinstance(until, bool) or not isinstance(until, int)
                              or not config.start_year <= until <= config.end_year):
        raise ValueError("bridge_reserve_until은 계획기간 안의 정수 연도여야 합니다.")
    floor = g.get("living_floor_monthly_2026")
    if floor is not None and (isinstance(floor, bool) or not isinstance(floor, (int, float)) or floor <= 0):
        raise ValueError("living_floor_monthly_2026은 0보다 큰 금액이어야 합니다.")
    cut = g.get("living_cut_years", 2)
    restore = g.get("living_restore_years", 3)
    for name, v in (("living_cut_years", cut), ("living_restore_years", restore)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 1:
            raise ValueError(f"{name}는 1 이상의 정수여야 합니다.")
    if restore < cut:
        raise ValueError("living_restore_years는 living_cut_years 이상이어야 합니다.")
    return {"bridge_reserve_until": until, "living_floor_monthly_2026": floor,
            "living_cut_years": cut, "living_restore_years": restore}


def _validate_flow(name, flow, allow_negative=False):
    """
    외부 모듈 입력 형식:
        {연도(int): 금액(int)}

    국민연금·퇴직급여:
        세후 명목 원화 현금유입

    주택:
        명목 원화 현금지출

    투자:
        명목 원화 투자손익
        손실은 음수 허용
    """

    if flow is None:
        return

    if not isinstance(flow, Mapping):
        raise TypeError(
            f"{name}은 연도별 금액 딕셔너리여야 합니다."
        )

    for year, amount in flow.items():
        if not isinstance(year, int):
            raise TypeError(
                f"{name}의 연도는 정수여야 합니다."
            )

        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
        ):
            raise TypeError(
                f"{name}의 금액은 정수 원화여야 합니다."
            )

        if not allow_negative and amount < 0:
            raise ValueError(
                f"{name}에는 음수 금액을 넣을 수 없습니다."
            )


def _validate_returns(investment_returns):
    if investment_returns is None:
        return
    if not isinstance(investment_returns, Mapping):
        raise TypeError("investment_returns는 {연도: 수익률} 딕셔너리여야 합니다.")
    for year, rate in investment_returns.items():
        if not isinstance(year, int) or isinstance(year, bool):
            raise TypeError("investment_returns의 연도는 정수여야 합니다.")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise TypeError("investment_returns의 수익률은 숫자여야 합니다.")
        if not math.isfinite(rate) or rate < -1:
            raise ValueError("투자수익률은 -1(=-100%) 이상 유한값이어야 합니다.")


def _investment_profit_for_year(
    year,
    investable_assets,
    investment_profits,
    investment_returns,
    investment_fn,
    investment_return_fn,
    investment_rng,
    state,
):
    """연말 투자손익.

    investable_assets = 해당 연도 소득·세금·지출·부모·주택·자녀지원을 모두 반영한 뒤,
    연말 투자손익 적용 직전의 금융자산(0 이하이면 0).

    - investment_profits {연도: 금액}: 하위호환·결정론적 테스트용. 금액을 그대로 사용.
    - investment_returns {연도: 수익률}: investable_assets × 수익률
    - investment_fn(year, investable_assets, state, investment_rng) -> profit
    - investment_return_fn(year, state) -> simple rate; annual-midpoint cashflow method
    """
    if investment_profits is not None:
        return investment_profits.get(year, 0), "fixed_profits"

    if investment_returns is not None:
        rate = investment_returns.get(year, 0.0)
        return round(investable_assets * rate), "returns"

    if investment_return_fn is not None:
        # The callback supplies the year's portfolio SIMPLE return after dynamic
        # weight selection. Investment gains are accrued using a midyear
        # cashflow approximation but are POSTED only at year end.
        rate = investment_return_fn(year, state)
        if isinstance(rate, bool) or not isinstance(rate, (int, float)):
            raise TypeError("investment_return_fn은 연간 단순수익률 숫자를 반환해야 합니다.")
        if not math.isfinite(rate) or rate < -1:
            raise ValueError("investment_return_fn의 수익률은 -100% 이상 유한값이어야 합니다.")
        opening = state["opening_assets"]
        net_flow = state["net_cashflow"]
        # 연말에 들어오는 유입(예: 66세 연말 퇴직급여 일시금)은 그해 운용기간이 0이다.
        year_end_inflow = state.get("year_end_inflow", 0)
        # A_end = A * (1+r) + (F - E) * sqrt(1+r) + E
        # profit = A*r + (F-E)*(sqrt(1+r)-1).
        profit = round(
            opening * rate
            + (net_flow - year_end_inflow) * (math.sqrt(1 + rate) - 1)
        )
        return profit, "returns_midyear_dynamic"

    if investment_fn is not None:
        profit = investment_fn(year, investable_assets, state, investment_rng)
        if isinstance(profit, bool) or not isinstance(profit, (int, float)):
            raise TypeError("investment_fn은 숫자 투자손익을 반환해야 합니다.")
        if not math.isfinite(profit):
            raise ValueError("investment_fn 반환값이 NaN 또는 inf입니다.")
        profit = round(profit)
        if investable_assets <= 0 and profit != 0:
            raise ValueError("투자가능자산이 0이면 투자손익도 0이어야 합니다.")
        if profit < -investable_assets:
            raise ValueError("투자손실이 투자가능자산을 초과할 수 없습니다.")
        return profit, "callback"

    return 0, "none"


def simulate(
    scenario=None,
    config=BASE_CONFIG,
    household=HOUSEHOLD,
    pension_flows=None,
    retirement_flows=None,
    housing_costs=None,
    investment_profits=None,
    random_seed=None,
    reemployment_state=None,
    parent_event_state=None,
    child_event_state=None,
    investment_returns=None,
    investment_fn=None,
    investment_return_fn=None,
    spending_policy=None,
    year_end_inflows=None,
    guardrails=None,
):
    """
    공통 생애 현금흐름 엔진.

    guardrails (기본 None = 꺼짐, 결과 기존과 동일):
        bridge_reserve_until: 정수 연도 | None
            규칙① 연금 공백기 준비금. 자녀 일회성 지원 전 준비금을
            max(다음 1년 필수지출, 다음 해~이 연도의 확정 필수 순지출 합)으로 넓힌다.
        living_floor_monthly_2026: 원 | None
            규칙② 생활비 가드레일(계획 장부만). 그해 초 금융자산이
            living_cut_years(기본 2)년치 확정 필수 순지출보다 적으면 생활비를 이 금액(물가 반영)으로
            낮추고, living_restore_years(기본 3)년치 이상이면 원래대로 되돌린다(그 사이는 이전 상태 유지).
        '확정 필수 순지출' = 계획 생활비 + 양가 부모 정기지원 + 진입한 장기요양비 + 주택상환
            − (기존 직장 세후임금 + 국민연금 + 퇴직급여). 재취업소득·미발생 확률사건은 넣지 않는다.

    외부 모듈 입력:
        pension_flows:
            {연도: 세후 국민연금 수입}

        retirement_flows:
            {연도: 세후 퇴직급여 현금유입}

        housing_costs:
            {연도: 주택 관련 현금지출}

        investment_profits:
            {연도: 투자손익}  (하위호환·결정론적 테스트용)

        investment_returns:
            {연도: 수익률}  -> 해당 path의 investable_assets × 수익률

        investment_fn:
            investment_fn(year, investable_assets, state, investment_rng) -> profit
            (Monte Carlo 권장 방식. investment_rng는 master seed에서 파생한
             투자 전용 스트림이므로 같은 seed에서 재현된다.)

        세 투자 입력 중 최대 하나만 지정한다.

    연도별 계산순서
        연초 자산 -> 소득(근로·재취업·국민연금·퇴직급여) -> 세금 -> 생활비
        -> 부모지원·부모이벤트 -> 주택비 -> 자녀지원(next-year reserve, cap)
        -> investable_assets 확정 -> 연말 투자손익 -> 연말 자산
        연말 확정 투자손익을 연중 자녀지원 능력에 미리 쓰지 않는다(look-ahead 금지).

    자산·부족액
        raw_closing_assets = opening_assets + net_cashflow + investment_profit
        closing_assets     = max(0, raw_closing_assets)
        unfunded_amount    = max(0, -raw_closing_assets)
        다음 연도 opening_assets = 당해 closing_assets (부족액은 부채로 이월하지 않음)
        누적 부족액은 cumulative_unfunded로 별도 추적한다.

    모든 금액은 해당 연도의 명목 원화.

    None:
        모듈 미연결

    {}:
        연결됐지만 해당 기간 금액이 0원

    주의:
        IRP 연금수령을 연결할 때는
        IRP 잔액과 인출액을 이중계상하면 안 됨.
    """

    if scenario is None:
        scenario = ScenarioConfig()

    # 최소 장부 생활비는 계획 생활비(변경 후 금액 포함) 이하여야 한다.
    plan_living_floor = config.monthly_living_cost
    if getattr(config, "monthly_living_cost_after_change", None) is not None:
        plan_living_floor = min(plan_living_floor, config.monthly_living_cost_after_change)
    spending_policy = validate_spending_policy(
        spending_policy, plan_monthly_living=plan_living_floor
    )
    validate_seed(random_seed)

    provided_investment = [
        x is not None
        for x in (investment_profits, investment_returns, investment_fn, investment_return_fn)
    ]
    if sum(provided_investment) > 1:
        raise ValueError(
            "investment_profits / investment_returns / investment_fn / investment_return_fn 중 하나만 지정하세요."
        )
    if investment_fn is not None and not callable(investment_fn):
        raise TypeError("investment_fn은 호출 가능한 함수여야 합니다.")
    if investment_return_fn is not None and not callable(investment_return_fn):
        raise TypeError("investment_return_fn은 호출 가능한 함수여야 합니다.")
    _validate_returns(investment_returns)
    investment_rng = (
        derive_rng(random_seed, "investment")
        if investment_fn is not None else None
    )

    if scenario.reemployment and reemployment_state is None:
        reemployment_state = sample_household_reemployment(
            random_seed=random_seed
        )

    if scenario.parent_events and parent_event_state is None:
        parent_event_state = sample_parent_events(
            scenario=scenario,
            config=config,
            random_seed=random_seed,
        )

    if scenario.child_events and child_event_state is None:
        child_event_state = sample_child_events(
            scenario=scenario,
            config=config,
            random_seed=random_seed,
        )

    validate_inputs(
        config=config,
        household=household,
        scenario=scenario,
    )

    _validate_flow(
        "pension_flows",
        pension_flows,
    )

    _validate_flow(
        "retirement_flows",
        retirement_flows,
    )

    _validate_flow(
        "housing_costs",
        housing_costs,
    )

    _validate_flow(
        "investment_profits",
        investment_profits,
        allow_negative=True,
    )

    # 연말 유입(퇴직급여 일시금 등): 반년복리 계산에서 그해 운용수익 0으로 처리할 금액.
    # 안전장치: 그해 퇴직급여 유입액을 넘을 수 없다.
    _validate_flow("year_end_inflows", year_end_inflows)
    if year_end_inflows is not None:
        for y, amount in year_end_inflows.items():
            available = (retirement_flows or {}).get(y, 0)
            if amount > available:
                raise ValueError(
                    f"year_end_inflows[{y}]({amount:,})가 그해 퇴직급여 유입({available:,})보다 큽니다."
                )

    persons = {
        person.key: person
        for person in household
    }

    a_person = persons["a"]
    spouse_person = persons["spouse"]

    guard = _validate_guardrails(guardrails, config)
    guard_living_cut = False

    def _known_net_need(y):
        """y년 확정 필수 순지출(0 이상). 계획기간 밖이면 0."""
        if y > config.end_year:
            return 0
        essential = _next_year_essential_reserve(
            y - 1, config, scenario, parent_event_state, housing_costs)
        wage = 0
        for person in (a_person, spouse_person):
            gross = calculate_regular_wage(person, y, config)
            wage += gross - calculate_tax(person, gross, y)
        inflow = (
            wage
            + (pension_flows or {}).get(y, 0)
            + (retirement_flows or {}).get(y, 0)
        )
        return max(0, essential - inflow)

    module_status = {
        "pension_status": (
            "연결"
            if pension_flows is not None
            else "미연결"
        ),
        "retirement_status": (
            "연결"
            if retirement_flows is not None
            else "미연결"
        ),
        "housing_status": (
            "연결"
            if housing_costs is not None
            else "미연결"
        ),
        "investment_status": (
            "연결"
            if any(provided_investment)
            else "미연결"
        ),
    }

    # 가족지원 종료는 확률형 자녀 이벤트 + deterministic cutoff
    # (자녀 45세, 부모 100세)로 확정되었다. config의 *_support_end_year는
    # 추가 수동 종료연도 입력용으로만 남아 있다.
    family_support_status = (
        f"cutoff 적용(자녀 {scenario.son_regular_support_end_age}세·"
        f"부모 {scenario.parent_cashflow_end_age}세)"
    )

    full_cashflow = (
        module_status["pension_status"] == "연결"
        and module_status["retirement_status"] == "연결"
        and module_status["housing_status"] == "연결"
    )
    if not full_cashflow:
        projection_status = "legacy / 최종 자산고갈 분석 사용 금지"
    elif module_status["investment_status"] == "연결":
        projection_status = "full cashflow(투자 연결, 세금 임시모형)"
    else:
        projection_status = "full cashflow(투자 미연결, 세금 임시모형)"

    results = []
    assets = config.initial_financial_assets

    cumulative_unfunded = 0
    first_unfunded_year = None

    # 실제로 지급된 일회성 자녀지원만 증여 이력으로 추적한다.
    child_gift_history = []

    for year in range(
        config.start_year,
        config.end_year + 1,
    ):
        # ---------------------------
        # 1. 기존 직장 근로소득
        # ---------------------------
        a_regular = calculate_regular_wage(
            a_person, year, config
        )

        spouse_regular = calculate_regular_wage(
            spouse_person, year, config
        )

        regular_wage = (
            a_regular + spouse_regular
        )

        # ---------------------------
        # 2. 재취업 소득
        # ---------------------------
        a_reemployment = calculate_reemployment_wage(
            a_person, year, config, scenario, reemployment_state
        )

        spouse_reemployment = (
            calculate_reemployment_wage(
                spouse_person,
                year,
                config,
                scenario,
                reemployment_state,
            )
        )

        reemployment_wage = (
            a_reemployment + spouse_reemployment
        )

        # ---------------------------
        # 3. 개인별 세금·사회보험료
        # ---------------------------
        a_gross = (
            a_regular + a_reemployment
        )

        spouse_gross = (
            spouse_regular + spouse_reemployment
        )

        a_tax = calculate_tax(
            a_person, a_gross, year
        )

        spouse_tax = calculate_tax(
            spouse_person, spouse_gross, year
        )

        gross_wage = a_gross + spouse_gross
        tax = a_tax + spouse_tax
        net_wage = gross_wage - tax

        # ---------------------------
        # 4. 외부 모듈 현금유입
        # ---------------------------
        pension = (
            pension_flows.get(year, 0)
            if pension_flows is not None
            else 0
        )

        retirement = (
            retirement_flows.get(year, 0)
            if retirement_flows is not None
            else 0
        )

        # ---------------------------
        # 5. 기본 지출
        # ---------------------------
        son_support_months = _son_support_months_for_year(
            year,
            scenario,
            child_event_state,
            config,
        )
        if (spending_policy["mode"] == "minimum"
                and "son" not in spending_policy["essential_family_support"]):
            # Minimum ledger does not pay optional regular child support.
            # Keep output son_support_months consistent with the actual expense.
            son_support_months = 0
        expenses = calculate_expenses(
            year,
            config,
            son_support_months=son_support_months,
            scenario=scenario,
        )
        expenses = apply_spending_policy(
            expenses,
            year=year,
            start_year=config.start_year,
            inflation_rate=config.inflation_rate,
            policy=spending_policy,
        )

        # 5-1. 규칙② 생활비 가드레일 (계획 장부만, guardrails 지정 시)
        guard_living_applied = False
        if (guard is not None
                and guard["living_floor_monthly_2026"] is not None
                and spending_policy["mode"] == "plan"):
            need_cut = sum(_known_net_need(y)
                           for y in range(year, year + guard["living_cut_years"]))
            need_restore = sum(_known_net_need(y)
                               for y in range(year, year + guard["living_restore_years"]))
            if assets < need_cut:
                guard_living_cut = True
            elif assets >= need_restore:
                guard_living_cut = False
            if guard_living_cut:
                floor_living = round(
                    guard["living_floor_monthly_2026"] * 12 * inflation_factor(year, config))
                if floor_living < expenses["living"]:
                    reduction = expenses["living"] - floor_living
                    expenses = dict(expenses)
                    expenses["living"] = floor_living
                    expenses["total"] -= reduction
                    guard_living_applied = True

        # ---------------------------
        # 6. 노부모 확률형 생애이벤트
        #    (비선택적 지출이므로 자녀 선택지원보다 먼저 반영)
        # ---------------------------
        parent_costs = calculate_parent_event_costs(
            year,
            config,
            scenario,
            parent_event_state=parent_event_state,
        )
        health_cost = parent_costs["total"]

        # ---------------------------
        # 7. 주택 관련 지출
        # ---------------------------
        housing = (
            housing_costs.get(year, 0)
            if housing_costs is not None
            else 0
        )

        # ---------------------------
        # 8. 자녀지원 전 예상 자산
        # ---------------------------
        total_income = (
            net_wage + pension + retirement
        )

        pre_child_total_expense = (
            expenses["total"]
            + health_cost
            + housing
        )
        pre_child_net_cashflow = (
            total_income - pre_child_total_expense
        )

        opening_assets = assets
        # 연말 투자손익은 자녀지원 이후에 반영한다(look-ahead 금지).
        pre_child_closing_assets = (
            opening_assets
            + pre_child_net_cashflow
        )

        # ---------------------------
        # 9. 자녀 독립·결혼 선택지원
        # ---------------------------
        child_event_info = _child_event_target_support(
            year,
            config,
            scenario,
            child_event_state,
        )
        # The minimum ledger excludes all optional child one-time transfers.
        # Keep the sampled child state (same future shocks), but never create
        # an affordability-dependent discretionary payment in this ledger.
        if not discretionary_child_one_time_allowed(spending_policy):
            child_event_info = {
                "event_type": None,
                "target_support_nominal": 0,
                "support_label": None,
                "marriage_event": False,
            }
        child_event_type = child_event_info["event_type"]
        child_target_support = child_event_info["target_support_nominal"]
        child_support_label = child_event_info["support_label"]

        child_essential_reserve = 0
        child_available_support = 0
        child_event_support = 0
        child_support_shortfall = 0
        child_tax_info = {
            "gift_amount": 0,
            "general_deduction_used": 0,
            "marriage_deduction_used": 0,
            "tax_base": 0,
            "estimated_gift_tax_child": 0,
            "child_net_after_gift_tax": 0,
            "tax_payer": "child",
            "household_cash_outflow_for_tax": 0,
        }

        if child_event_type is not None:
            child_essential_reserve = _next_year_essential_reserve(
                year,
                config,
                scenario,
                parent_event_state,
                housing_costs,
            )
            # 규칙① 연금 공백기 준비금 (guardrails 지정 시)
            if (guard is not None
                    and guard["bridge_reserve_until"] is not None
                    and year < guard["bridge_reserve_until"]):
                bridge = sum(_known_net_need(y)
                             for y in range(year + 1, guard["bridge_reserve_until"] + 1))
                child_essential_reserve = max(child_essential_reserve, bridge)
            child_available_support = max(
                0,
                pre_child_closing_assets - child_essential_reserve,
            )
            child_event_support = min(
                child_target_support,
                child_available_support,
            )
            child_support_shortfall = max(
                0,
                child_target_support - child_event_support,
            )

            if child_event_support > 0:
                child_tax_info = estimate_child_gift_tax(
                    gift_amount=child_event_support,
                    year=year,
                    prior_gifts=child_gift_history,
                    marriage_event=child_event_info["marriage_event"],
                )
                child_gift_history.append({
                    "year": year,
                    "amount": child_event_support,
                    "event_type": child_event_type,
                })

        # ---------------------------
        # 10. 최종 현금흐름 및 자산 갱신
        # ---------------------------
        total_expense = (
            pre_child_total_expense
            + child_event_support
        )
        net_cashflow = (
            total_income - total_expense
        )
        # ---------------------------
        # 10-1. 투자가능자산 확정 후 연말 투자손익
        # ---------------------------
        pre_investment_assets = (
            pre_child_closing_assets
            - child_event_support
        )
        investable_assets = max(0, pre_investment_assets)
        investment_state = {
            "year": year,
            "opening_assets": opening_assets,
            "investable_assets": investable_assets,
            "pre_investment_assets": pre_investment_assets,
            "net_cashflow": net_cashflow,
            "year_end_inflow": (
                year_end_inflows.get(year, 0) if year_end_inflows is not None else 0
            ),
            "a_age": get_age(a_person, year),
            "spouse_age": get_age(spouse_person, year),
            "son_age": son_age(year, config),
            "parent_age": parent_age(year, config, scenario),
            "reemployment_state": reemployment_state,
            "parent_event_state": parent_event_state,
            "child_event_state": child_event_state,
            "investment_rng_stream": (
                f"{random_seed}:investment" if random_seed is not None else None
            ),
        }
        investment_profit, investment_mode = _investment_profit_for_year(
            year,
            investable_assets,
            investment_profits,
            investment_returns,
            investment_fn,
            investment_return_fn,
            investment_rng,
            investment_state,
        )

        raw_closing_assets = (
            pre_investment_assets
            + investment_profit
        )

        # 자산이 부족하면 잔액은 0원으로 두고
        # 충당하지 못한 금액을 별도 기록한다.
        unfunded_amount = max(
            0, -raw_closing_assets
        )

        assets = max(
            0, raw_closing_assets
        )

        cumulative_unfunded += unfunded_amount

        if (
            unfunded_amount > 0
            and first_unfunded_year is None
        ):
            first_unfunded_year = year

        # ---------------------------
        # 10. 2026년 구매력 환산
        # ---------------------------
        real_assets = round(
            assets / inflation_factor(year, config)
        )

        # ---------------------------
        # 11. 결과 저장
        # ---------------------------
        results.append({
            "scenario": scenario.name,
            "spending_mode": spending_policy["mode"],
            "year": year,

            "a_age": get_age(a_person, year),
            "spouse_age": get_age(
                spouse_person, year
            ),

            "a_regular_wage": a_regular,
            "spouse_regular_wage": spouse_regular,
            "regular_wage": regular_wage,

            "a_reemployment_wage": a_reemployment,
            "spouse_reemployment_wage": (
                spouse_reemployment
            ),
            "reemployment_wage": reemployment_wage,

            "reemployment_mode": (
                "KLoSA Beta-Binomial"
                if scenario.reemployment else "없음"
            ),
            "a_reemployment_success": (
                reemployment_state["a"]["success"]
                if reemployment_state is not None else False
            ),
            "spouse_reemployment_success": (
                reemployment_state["spouse"]["success"]
                if reemployment_state is not None else False
            ),
            "a_reemployment_duration_years": (
                reemployment_state["a"]["duration_years"]
                if reemployment_state is not None else 0
            ),
            "spouse_reemployment_duration_years": (
                reemployment_state["spouse"]["duration_years"]
                if reemployment_state is not None else 0
            ),

            "gross_wage": gross_wage,
            "a_tax_and_insurance": a_tax,
            "spouse_tax_and_insurance": spouse_tax,
            "tax_and_insurance": tax,
            "net_wage": net_wage,

            "national_pension": pension,
            "retirement_benefit": retirement,
            "total_income": total_income,

            "living_cost": expenses["living"],
            "son_support": expenses["son"],
            "a_mother_support": expenses["a_mother"],
            "spouse_mother_support": (
                expenses["spouse_mother"]
            ),
            "family_support": (
                expenses["family_support"]
            ),

            # 자녀 독립·결혼 이벤트
            "son_age": son_age(year, config),
            "parent_age": parent_age(year, config, scenario),
            "parent_cashflow_active": parent_cashflow_active(year, config, scenario),
            "son_support_months": son_support_months,
            # 동거 상태와 정기지원 상태는 분리한다.
            # 자녀 이벤트 OFF이면 계속 동거로 본다. 이벤트 발생연도(연중)부터 비동거.
            "son_co_resident": (
                True
                if child_event_state is None
                or child_event_state.get("first_exit_year") is None
                else year < child_event_state["first_exit_year"]
            ),
            "son_regular_support_active": son_support_months > 0,
            "son_independence_year": (
                child_event_state.get("independence_year")
                if child_event_state is not None else None
            ),
            "son_marriage_year": (
                child_event_state.get("marriage_year")
                if child_event_state is not None else None
            ),
            "son_first_exit_type": (
                child_event_state.get("first_exit_type")
                if child_event_state is not None else None
            ),
            "son_child_event_model_through_age": (
                child_event_state.get("modeled_through_age")
                if child_event_state is not None else None
            ),
            "son_event_type_this_year": child_event_type,
            "son_support_bracket": child_support_label,
            "son_target_one_time_support": child_target_support,
            "son_pre_support_projected_assets": pre_child_closing_assets,
            "son_next_year_essential_reserve": child_essential_reserve,
            "son_available_support_capacity": child_available_support,
            "son_actual_one_time_support": child_event_support,
            "son_support_capacity_shortfall": child_support_shortfall,
            "son_gift_general_deduction_used": (
                child_tax_info["general_deduction_used"]
            ),
            "son_gift_marriage_deduction_used": (
                child_tax_info["marriage_deduction_used"]
            ),
            "son_gift_tax_base": child_tax_info["tax_base"],
            "son_estimated_gift_tax_child": (
                child_tax_info["estimated_gift_tax_child"]
            ),
            "son_net_received_after_gift_tax": (
                child_tax_info["child_net_after_gift_tax"]
            ),
            "son_gift_tax_payer": child_tax_info["tax_payer"],
            "household_gift_tax_outflow": (
                child_tax_info["household_cash_outflow_for_tax"]
            ),

            "a_mother_stroke_event_year": (
                parent_event_state["a_mother_stroke_year"]
                if parent_event_state is not None else None
            ),
            "a_mother_stroke_cost": parent_costs["a_mother_stroke_cost"],
            "spouse_mother_ltc_entry_year": (
                parent_event_state["spouse_mother_ltc_entry_year"]
                if parent_event_state is not None else None
            ),
            "spouse_mother_ltc_cost": parent_costs["spouse_mother_ltc_cost"],
            "parent_event_cost": health_cost,
            # 기존 결과 소비 코드 호환을 위한 별칭
            "health_shock_cost": health_cost,
            "housing_cost": housing,
            "total_expense": total_expense,

            "net_cashflow": net_cashflow,

            "opening_assets": opening_assets,
            "investable_assets": investable_assets,
            "investment_mode": investment_mode,
            "investment_profit": investment_profit,
            "raw_closing_assets": raw_closing_assets,
            "closing_assets": assets,
            "real_assets_2026": real_assets,

            "unfunded_amount": unfunded_amount,
            "cumulative_unfunded": (
                cumulative_unfunded
            ),
            "first_unfunded_year": (
                first_unfunded_year
            ),

            **module_status,
            **({"guardrail_living_cut": guard_living_applied} if guard is not None else {}),

            "family_support_status": family_support_status,

            "tax_model_status": "임시 추정",
            "projection_status": projection_status,
        })

    return results
