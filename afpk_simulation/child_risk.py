"""자녀 독립·결혼 생애이벤트 확률 샘플링.

현재 페르소나
- 2026년 만 27세 남성, 미혼, 부모와 동거.
- 비혼 단순독립과 결혼은 경쟁위험으로 처리한다.
- 부모동거 상태에서는 해당 연도 혼인 여부를 먼저 추첨하고,
  혼인이 없을 때만 비혼 단순독립을 추첨한다.
- 비혼 독립 후에도 만 44세까지 혼인확률을 계속 적용한다.
- 연령구간: 27~29 / 30~34 / 35~39 / 40~44세.
  만 45세부터 신규 독립·결혼을 추첨하지 않는다(scenario.son_event_max_age=44).
- 확률표는 scenarios.py의 ScenarioConfig 한 곳에서 관리한다.
- 난수는 master seed에서 파생한 자녀 전용 스트림을 사용한다(rng_streams.py).

지원금
- 비혼 단순독립 시 부모의 주거지원 여부를 별도로 추첨한다.
- 결혼 시에는 남편측 부모의 결혼주거자금 지원 구간 자체를 추첨한다.
- 실제 지급액은 여기서 정하지 않고, engine.py에서 당시 가구 지급능력으로 상한을 건다.
"""
from __future__ import annotations

from rng_streams import derive_rng


def _rng_for_child_events(random_seed=None):
    """master seed에서 파생한 자녀이벤트 전용 난수 스트림."""
    return derive_rng(random_seed, "child")


def _age_bucket(age, scenario):
    """신규 이벤트 추첨 연령구간. 범위 밖(45세 이상 등)이면 None."""
    if age > scenario.son_event_max_age:
        return None
    if 27 <= age <= 29:
        return "27_29"
    if 30 <= age <= 34:
        return "30_34"
    if 35 <= age <= 39:
        return "35_39"
    if 40 <= age <= 44:
        return "40_44"
    return None


def _marriage_probability(age, scenario):
    bucket = _age_bucket(age, scenario)
    if bucket is None:
        return 0.0
    return getattr(scenario, f"son_marriage_probability_{bucket}")


def _simple_independence_probability(age, scenario):
    bucket = _age_bucket(age, scenario)
    if bucket is None:
        return 0.0
    return getattr(scenario, f"son_independence_probability_{bucket}")


def _sample_marriage_support_bracket(rng, scenario):
    """남편측 부모 결혼주거지원금 분포에서 구간을 1회 추첨."""
    brackets = scenario.son_marriage_support_brackets_2015
    u = rng.random()
    cumulative = 0.0
    for item in brackets:
        cumulative += item["probability"]
        if u < cumulative:
            return dict(item)
    # 부동소수점 누적 오차 방지
    return dict(brackets[-1])


def sample_child_events(scenario, config, random_seed=None):
    """한 Monte Carlo 경로의 자녀 독립/결혼 상태를 추출한다.

    반환값은 '사건 발생연도와 통계상 목표지원금 구간'만 담는다.
    실제 지원금은 당시 가구의 자산·소득·지출을 반영하여 엔진에서 계산한다.
    """
    rng = _rng_for_child_events(random_seed)

    birth_year = config.start_year - config.son_age_2026
    status = "cohabiting_unmarried"
    independence_year = None
    marriage_year = None
    first_exit_year = None
    first_exit_type = None
    independence_support_selected = False
    marriage_support_bracket = None

    for year in range(config.start_year, config.end_year + 1):
        age = year - birth_year
        if age < config.son_age_2026:
            continue
        # 만 45세부터 신규 결혼·독립 추첨 없음 (44세까지 추첨 가능)
        if age > scenario.son_event_max_age:
            break

        marriage_p = _marriage_probability(age, scenario)
        independence_p = _simple_independence_probability(age, scenario)

        if status == "cohabiting_unmarried":
            # 결혼 동시독립이 먼저인 경쟁위험 구조.
            if rng.random() < marriage_p:
                marriage_year = year
                first_exit_year = year
                first_exit_type = "marriage_from_cohabitation"
                marriage_support_bracket = _sample_marriage_support_bracket(
                    rng, scenario
                )
                status = "married"
                break

            # 결혼이 없을 때만 비혼 단순독립을 추첨.
            if rng.random() < independence_p:
                independence_year = year
                first_exit_year = year
                first_exit_type = "simple_independence"
                independence_support_selected = (
                    rng.random() < scenario.son_independence_support_probability
                )
                status = "independent_unmarried"
                continue

        elif status == "independent_unmarried":
            if rng.random() < marriage_p:
                marriage_year = year
                marriage_support_bracket = _sample_marriage_support_bracket(
                    rng, scenario
                )
                status = "married"
                break

    return {
        "initial_status": "cohabiting_unmarried",
        "final_status": status,
        "independence_year": independence_year,
        "marriage_year": marriage_year,
        "first_exit_year": first_exit_year,
        "first_exit_type": first_exit_type,
        "independence_support_selected": independence_support_selected,
        "marriage_support_bracket": marriage_support_bracket,
        "modeled_through_age": scenario.son_event_max_age,
    }
