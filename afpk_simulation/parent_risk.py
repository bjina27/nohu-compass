"""노부모 생애이벤트 확률 샘플링.

모델 목적
- A씨 어머니: 83세 이후 최초 뇌졸중 발생 여부를 매년 추첨.
- 배우자 어머니: 83세 이후 최초 장기요양 인정 여부를 연령구간별로 매년 추첨.
- 사망, 재발, 장기요양 등급변화, 시설입소 전환은 모델링하지 않는다.
- 만 100세 cutoff: 사망을 직접 모델링하는 대신 장기 시뮬레이션용
  deterministic cutoff로 만 100세부터 신규 stroke·LTC 진입을 추첨하지 않는다.
  (scenario.parent_cashflow_end_age, 기본 100)

모든 확률은 연간 확률이며, 최초 사건이 발생한 뒤 같은 사건을 다시 추첨하지 않는다.
"""
from rng_streams import derive_rng


def _rng_for_parent_events(random_seed=None):
    """master seed에서 파생한 부모이벤트 전용 난수 스트림."""
    return derive_rng(random_seed, "parent")


def _first_event_year(start_year, end_year, probability_for_age, age_for_year, rng):
    for year in range(start_year, end_year + 1):
        age = age_for_year(year)
        p = probability_for_age(age)
        if not 0 <= p <= 1:
            raise ValueError("연간 사건확률은 0~1 사이여야 합니다.")
        if rng.random() < p:
            return year
    return None


def sample_parent_events(scenario, config, random_seed=None):
    """한 Monte Carlo 경로의 부모 사건 발생연도를 한 번만 추출한다."""
    rng = _rng_for_parent_events(random_seed)
    mother_birth_year = config.start_year - scenario.parent_mother_age_2026
    age_for_year = lambda year: year - mother_birth_year
    end_age = scenario.parent_cashflow_end_age

    a_stroke_year = _first_event_year(
        config.start_year,
        config.end_year,
        probability_for_age=lambda age: (
            scenario.a_mother_stroke_annual_probability
            if 83 <= age < end_age else 0.0
        ),
        age_for_year=age_for_year,
        rng=rng,
    )

    def spouse_ltc_probability(age):
        if age < 83 or age >= end_age:
            return 0.0
        if age <= 84:
            return scenario.spouse_mother_ltc_probability_83_84
        return scenario.spouse_mother_ltc_probability_85plus

    spouse_ltc_year = _first_event_year(
        config.start_year,
        config.end_year,
        probability_for_age=spouse_ltc_probability,
        age_for_year=age_for_year,
        rng=rng,
    )

    return {
        "a_mother_stroke_year": a_stroke_year,
        "spouse_mother_ltc_entry_year": spouse_ltc_year,
    }
