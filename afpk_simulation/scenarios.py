from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioConfig:
    name: str = "기본"

    # 생애이벤트 ON/OFF
    reemployment: bool = False
    parent_events: bool = False
    child_events: bool = False

    # ---------------------------
    # 재취업 이벤트
    # ---------------------------
    # KLoSA 기반 대표 재취업 월소득(2026년 구매력 기준)
    # 발생/지속 여부는 reemployment_risk.py의 Beta-Binomial로만 결정한다.
    a_reemployment_monthly: int = 1_200_000
    spouse_reemployment_monthly: int = 2_398_000

    # ---------------------------
    # 노부모 생애이벤트
    # ---------------------------
    # 두 어머니 모두 2026년 83세로 시작.
    parent_mother_age_2026: int = 83

    # A씨 어머니: 83세 이후 최초 뇌졸중
    a_mother_stroke_annual_probability: float = 0.0169
    a_mother_stroke_cost_2026: int = 2_969_853

    # 배우자 어머니: 최초 장기요양 인정
    spouse_mother_ltc_probability_83_84: float = 0.0729
    spouse_mother_ltc_probability_85plus: float = 0.1351
    spouse_mother_ltc_annual_cost_2026: int = 2_029_968

    # 부모 관련 현금흐름 deterministic cutoff.
    # 부모 사망은 확률적으로 모델링하지 않는다(팀 결정). 대신 만 99세까지 기존 로직,
    # 만 100세부터 정기 부모지원·LTC 반복비용 0, 신규 stroke·LTC 진입 추첨 없음.
    # 실제 생존모형이 아닌 장기 시뮬레이션 단순화 가정이므로 평균 지원기간이 길게 잡힐 수 있다.
    parent_cashflow_end_age: int = 100

    # ---------------------------
    # 자녀 독립·결혼 이벤트
    # ---------------------------
    # 자녀 확률표는 이 영역에서만 관리한다 (child_risk.py가 참조).
    #
    # [단순 독립] 미혼·부모동거 자녀의 연간 비혼 단순독립 확률
    # - 27~29, 30~34: 기존 근거·계산방식 유지 (Parameter Freeze)
    # - 35~39: 미혼자 부모동거율 50.3%(35~39) -> 44.1%(40~44)를
    #   5년 동일 hazard로 연환산한 근사값: 1 - (0.441/0.503)^(1/5) ≈ 0.0260
    #   (통계청 연구보고서 「한국사회의 혼인·출산 특성과 이행」, 인구주택총조사 20% 표본)
    #   패널에서 직접 관측한 독립 hazard가 아니라 횡단면 부모동거율 감소의 연환산 근사치다.
    # - 40~44: 동일 기준 전국 45~49세 부모동거율이 없어 35~39 값을 연장한 모델링 가정.
    #   (수도권 미혼자 부모동거율 30~39세 51.0% -> 40~49세 40.9% 감소는 방향성 참고만)
    # - 연령구간별 독립확률은 이용 가능한 부모동거 통계의 조사시점 및 집계기준 차이로
    #   인해 완전한 단조형태를 가정하지 않는다.
    son_independence_probability_27_29: float = 0.04073
    son_independence_probability_30_34: float = 0.02024
    son_independence_probability_35_39: float = 0.0260
    son_independence_probability_40_44: float = 0.0260

    # [결혼] 미혼 남성의 연간 초혼확률 = 남성 초혼율(‰) / 해당 연령 남성 미혼율
    # 2024년 통계청 혼인·이혼 통계(연령별 남성 초혼율) + 2024 인구주택총조사(미혼율).
    # 초혼 기준이므로 재혼은 분자에 포함하지 않는다.
    # - 27~29: 25~29세 구간 22.38‰ / 95.0% ≈ 0.0236 (25~29세 통계 적용 근사값)
    # - 30~34: 47.22‰ / 74.7% ≈ 0.0632
    # - 35~39: 24.63‰ / 46.8% ≈ 0.0526
    # - 40~44: 7.20‰ / 30.1% ≈ 0.0239
    # 변경 이력: 27~29 0.0247 -> 0.0236, 30~34 0.0723 -> 0.0632
    #   (기존값은 전체 혼인율 기반이어서 재혼이 포함되어 있었음)
    son_marriage_probability_27_29: float = 0.0236
    son_marriage_probability_30_34: float = 0.0632
    son_marriage_probability_35_39: float = 0.0526
    son_marriage_probability_40_44: float = 0.0239

    # 신규 독립·결혼 추첨 마지막 연령(만 44세까지 추첨, 만 45세부터 없음)
    son_event_max_age: int = 44
    # 자녀 정기 현금지원 deterministic cutoff: 만 45세가 되는 해부터 0원.
    # 동거 여부(co_resident)와 정기지원 여부(regular_support_active)는 별개 상태다.
    son_regular_support_end_age: int = 45

    # 비혼 단순독립 시 부모 주거지원 여부
    son_independence_support_probability: float = 0.511
    # 2024년 청년 보증부월세 보증금 2,900만원 × 부모부담 60.9%
    # 이 값은 2024년 명목금액이며 엔진에서 2026년 가치로 보정한다.
    son_independence_support_amount_2024: int = 17_661_000

    # 결혼주거지원 구간: 2015년 가격 기준 남편측 부모 지원 분포.
    # 열린 상위구간(1.2억원 이상)은 임의 평균 역산 대신 하한 1.2억원을 대표값으로 사용.
    son_marriage_support_brackets_2015: tuple = (
        {"label": "none", "probability": 0.423, "representative_amount": 0},
        {"label": "under_30m", "probability": 0.077, "representative_amount": 15_000_000},
        {"label": "30m_60m", "probability": 0.184, "representative_amount": 45_000_000},
        {"label": "60m_90m", "probability": 0.077, "representative_amount": 75_000_000},
        {"label": "90m_120m", "probability": 0.097, "representative_amount": 105_000_000},
        {"label": "120m_plus", "probability": 0.142, "representative_amount": 120_000_000},
    )

    # 결혼지원 과거금액을 2026년 가치로 통일하기 위한 CPI 연결값.
    marriage_support_cpi_2015: float = 94.861
    marriage_support_cpi_2025: float = 116.72

    # 독립/결혼 발생연도에는 평균적으로 연중 중간에 사건이 발생한다고 보고
    # 기존 월 38.2만원 지원은 6개월분만 지급한다.
    son_support_months_in_exit_year: int = 6


SCENARIOS = {
    "base": ScenarioConfig(name="기본"),

    "reemployment": ScenarioConfig(
        name="재취업 확률형(KLoSA Beta-Binomial)",
        reemployment=True,
    ),

    "health": ScenarioConfig(
        name="노부모 확률형 생애이벤트",
        parent_events=True,
    ),

    # 이전 버전의 combined 의미는 호환성을 위해 유지.
    "combined": ScenarioConfig(
        name="재취업 확률형 + 노부모 생애이벤트",
        reemployment=True,
        parent_events=True,
    ),

    "child": ScenarioConfig(
        name="자녀 독립·결혼 확률형 생애이벤트",
        child_events=True,
    ),

    # 최신 전체 생애이벤트 통합 시나리오.
    "full": ScenarioConfig(
        name="재취업 + 노부모 + 자녀 생애이벤트",
        reemployment=True,
        parent_events=True,
        child_events=True,
    ),
}
