"""2026년 페르소나 기준 주택담보대출 원리금균등 상환 스케줄.

'cashflows'는 엔진 housing_costs용 연도별 *명목* 현금지출(원리금 합계).
'balances'는 자산현금흐름에 더하지 않는 부채 잔액이다.
보유세/수선비/보험료/주택가격변동 등은 아직 포함하지 않는다.
"""
from dataclasses import dataclass
from config import BASE_CONFIG


@dataclass(frozen=True)
class HousingResult:
    monthly_payment: int
    cashflows: dict[int, int]
    mortgage_balances: dict[int, int]
    principal_repayments: dict[int, int]
    interest_payments: dict[int, int]
    home_equity: dict[int, int]


def build_housing_flows(config=BASE_CONFIG) -> HousingResult:
    """매월 상환액을 계산한 뒤 연도별 합산 결과를 반환한다.

    가정: 시작연도 1월부터 매월 말 상환, 고정금리,
    주택가격 동결, 상환기간 중 추가대출/중도상환 없음.
    """
    balance = config.mortgage_balance_2026
    annual_rate = config.mortgage_annual_rate
    years = config.mortgage_remaining_years
    home_value = config.home_value_2026

    if config.end_year < config.start_year:
        raise ValueError("종료연도가 시작연도보다 빠릅니다.")
    if balance < 0 or home_value < 0:
        raise ValueError("주택가치와 대출잔액은 음수일 수 없습니다.")
    if not (0 <= annual_rate <= 1):
        raise ValueError("연 대출금리는 0~1의 소수로 입력하세요.")
    if not isinstance(years, int) or years <= 0:
        raise ValueError("대출 잔여기간은 양의 정수 연도여야 합니다.")
    if config.mortgage_repayment_type != "equal_payment":
        raise ValueError("현재는 원리금균등상환(equal_payment)만 지원합니다.")

    months = years * 12
    monthly_rate = annual_rate / 12
    if balance == 0:
        monthly_payment = 0
    elif monthly_rate == 0:
        monthly_payment = round(balance / months)
    else:
        monthly_payment = round(
            balance * monthly_rate / (1 - (1 + monthly_rate) ** (-months))
        )

    cashflows = {}
    mortgage_balances = {}
    principal_repayments = {}
    interest_payments = {}
    home_equity = {}

    for year in range(config.start_year, config.end_year + 1):
        annual_payment = 0
        annual_principal = 0
        annual_interest = 0

        for month in range(12):
            month_index = (year - config.start_year) * 12 + month
            if month_index >= months or balance <= 0:
                continue

            interest = round(balance * monthly_rate)
            # 마지막 회차에서 원 단위 반올림 잔액까지 전액 상환
            payment = min(monthly_payment, balance + interest)
            principal = payment - interest
            if principal < 0:
                raise ValueError("월 납부액이 이자보다 작아 상환할 수 없습니다.")

            balance -= principal
            annual_payment += payment
            annual_principal += principal
            annual_interest += interest

        cashflows[year] = annual_payment
        mortgage_balances[year] = balance
        principal_repayments[year] = annual_principal
        interest_payments[year] = annual_interest
        home_equity[year] = home_value - balance

    return HousingResult(
        monthly_payment=monthly_payment,
        cashflows=cashflows,
        mortgage_balances=mortgage_balances,
        principal_repayments=principal_repayments,
        interest_payments=interest_payments,
        home_equity=home_equity,
    )
