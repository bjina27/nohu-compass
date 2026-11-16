
from dataclasses import dataclass


@dataclass(frozen=True)
class Person:
    key: str
    name: str
    birth_year: int
    annual_wage_2026: int

    # 개인별 임금상승률 (확정 모델 입력값)
    # KLoSA 2018~2024 동일인·동일직장 유지 임금근로자의 2년간 임금변화율을
    # 연환산한 중앙값. 여성 57~64세 551건(고유 339명) -> 3.08%,
    # 남성 59~64세 476건(고유 317명) -> 0.83%.
    # 개인의 실제 미래임금이 아니라 통계 기반 모델 적용값이다.
    wage_growth_rate: float

    # 2026년 개인별 세금·사회보험료 추정액
    deduction_2026: int

    # 60세 이후 임시 차감률 [KNOWN LIMITATION]
    # 이번 버전에서는 공식 세법·보험료 산식으로 교체하지 않는다(후속 과제).
    deduction_rate_60plus: float

    retirement_age: int = 66
    nps_contribution_end_age: int = 60


@dataclass(frozen=True)
class BaseConfig:
    start_year: int = 2026
    end_year: int = 2069

    # 경제 가정
    inflation_rate: float = 0.022
    

    # 2026년 초기 금융자산
    initial_financial_assets: int = 70_130_000
    
    #자동차등
    other_nonfinancial_assets_2026=23_000_000
    
    #주택자산 (2026년 기준)
    home_value_2026: int = 330_000_000
    
    #주택담보대출
    mortgage_balance_2026: int = 109_780_000
    mortgage_annual_rate: float = 0.045
    mortgage_remaining_years: int = 12
    mortgage_repayment_type: str = "equal_payment"


    # 2026년 가구 기준 검증값
    base_gross_income: int = 75_000_000
    base_tax_and_insurance: int = 9_286_000

    # 부부 2인 생활비
    monthly_living_cost: int = 2_958_000

    # 생활비 변경 (상담 결정 변수). 둘 다 None이면 변경 없음.
    # living_cost_change_year부터 월 생활비를 monthly_living_cost_after_change로 바꾼다.
    # 금액은 2026년 가치이며 해당 연도 물가를 곱해 명목화한다.
    # 예: 2027년부터 월 30만 원 절감 → (2027, 2_658_000), 은퇴 시점부터 → (2036, ...)
    living_cost_change_year: int | None = None
    monthly_living_cost_after_change: int | None = None

    # 가족지원비
    # 자녀는 2026년 기준 만 27세 남성, 미혼, 부모동거
    son_age_2026: int = 27
    monthly_son_support: int = 382_000
    annual_a_mother_support: int = 2_138_000
    annual_spouse_mother_support: int = 1_567_000

    # 수동 마지막 지원연도(해당 연도까지 지급). None = 수동 종료연도 없음.
    # 가족지원 종료는 엔진의 deterministic cutoff로 처리된다:
    #   자녀 정기지원 만 45세부터 0 (ScenarioConfig.son_regular_support_end_age)
    #   부모 정기지원·LTC 만 100세부터 0 (ScenarioConfig.parent_cashflow_end_age)
    # 아래 값은 cutoff보다 이른 수동 종료가 필요할 때만 사용한다.
    son_support_end_year: int | None = None
    a_mother_support_end_year: int | None = None
    spouse_mother_support_end_year: int | None = None


A = Person(
    key="a",
    name="A씨",
    birth_year=1969,
    annual_wage_2026=27_720_000,
    wage_growth_rate=0.0308,
    deduction_2026=2_975_000,
    deduction_rate_60plus=0.0634,
)

SPOUSE = Person(
    key="spouse",
    name="배우자",
    birth_year=1967,
    annual_wage_2026=47_280_000,
    wage_growth_rate=0.0083,
    deduction_2026=6_311_000,
    deduction_rate_60plus=0.0938,
)

HOUSEHOLD = (A, SPOUSE)

BASE_CONFIG = BaseConfig()
