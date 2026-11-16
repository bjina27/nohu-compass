
from dataclasses import dataclass
from collections.abc import Mapping

from config import BASE_CONFIG
from strategies.payout import PayoutStrategy


@dataclass(frozen=True)
class RetirementSpec:
    person_key: str
    retirement_year: int

    # 팀원 계산 결과: 세전 퇴직급여 추정치
    gross_benefit_estimate: int

    # 일시금 선택 시 세후 수령액
    net_lump_sum: int | None = None

    # 연금 선택 시 연도별 세후 IRP 인출액
    net_annuity_by_year: Mapping[int, int] | None = None

    # 연금 선택 시 연도별 IRP 기말 잔액
    irp_balance_by_year: Mapping[int, int] | None = None


@dataclass(frozen=True)
class RetirementFlowResult:
    cashflows: dict[int, int]
    irp_balances: dict[int, int]
    selected_methods: dict[str, str]


RETIREMENT_SPECS = (
    RetirementSpec(
        person_key="a",
        retirement_year=2035,
        gross_benefit_estimate=69_800_000,
    ),
    RetirementSpec(
        person_key="spouse",
        retirement_year=2033,
        gross_benefit_estimate=116_890_000,
    ),
)


def _check_schedule(
    schedule,
    retirement_year,
    label,
):
    if not isinstance(schedule, Mapping):
        raise TypeError(
            f"{label}은 연도별 금액 딕셔너리여야 합니다."
        )

    for year, amount in schedule.items():
        if not isinstance(year, int):
            raise TypeError(
                f"{label}: 연도는 정수여야 합니다."
            )

        if year < retirement_year:
            raise ValueError(
                f"{label}: 퇴직 전 연도가 포함되었습니다."
            )

        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount < 0
        ):
            raise ValueError(
                f"{label}: 금액은 0 이상의 정수여야 합니다."
            )


def build_retirement_flows(
    specs,
    strategy: PayoutStrategy,
    config=BASE_CONFIG,
):
    """
    퇴직급여 수령 전략을 기본 엔진 입력으로 변환.

    일시금:
        퇴직연도에 세후 금액 한 번 유입

    연금:
        연도별 세후 IRP 인출액 유입
        IRP 잔액은 별도 보관

    주의:
        세전 퇴직급여 추정액은 참고값.
        세후 계산이 완료되지 않으면 연결 금지.
    """
    cashflows = {}
    irp_balances = {}
    selected_methods = {}
    seen_keys = set()

    for spec in specs:
        key = spec.person_key

        if key in seen_keys:
            raise ValueError(
                f"퇴직급여 대상자 중복: {key}"
            )

        seen_keys.add(key)

        method = strategy.method_for(key)
        selected_methods[key] = method

        if method == "lump_sum":
            if spec.net_lump_sum is None:
                raise ValueError(
                    f"{key}: 세후 일시금이 없습니다."
                )

            if (
                not isinstance(spec.net_lump_sum, int)
                or isinstance(spec.net_lump_sum, bool)
                or spec.net_lump_sum < 0
            ):
                raise ValueError(
                    f"{key}: 세후 일시금이 잘못되었습니다."
                )

            year = spec.retirement_year

            if config.start_year <= year <= config.end_year:
                cashflows[year] = (
                    cashflows.get(year, 0)
                    + spec.net_lump_sum
                )

        elif method == "annuity":
            if spec.net_annuity_by_year is None:
                raise ValueError(
                    f"{key}: 세후 연금수령 일정이 없습니다."
                )

            if spec.irp_balance_by_year is None:
                raise ValueError(
                    f"{key}: IRP 잔액 일정이 없습니다."
                )

            _check_schedule(
                spec.net_annuity_by_year,
                spec.retirement_year,
                f"{key} 연금수령",
            )

            _check_schedule(
                spec.irp_balance_by_year,
                spec.retirement_year,
                f"{key} IRP 잔액",
            )

            if not spec.net_annuity_by_year:
                raise ValueError(
                    f"{key}: 연금수령 일정이 비어 있습니다."
                )

            for year, amount in (
                spec.net_annuity_by_year.items()
            ):
                if config.start_year <= year <= config.end_year:
                    cashflows[year] = (
                        cashflows.get(year, 0)
                        + amount
                    )

            for year, balance in (
                spec.irp_balance_by_year.items()
            ):
                if config.start_year <= year <= config.end_year:
                    irp_balances[year] = (
                        irp_balances.get(year, 0)
                        + balance
                    )

    return RetirementFlowResult(
        cashflows=cashflows,
        irp_balances=irp_balances,
        selected_methods=selected_methods,
    )
