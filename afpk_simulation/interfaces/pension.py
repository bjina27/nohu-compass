
from dataclasses import dataclass
from collections.abc import Mapping

from config import BASE_CONFIG


@dataclass(frozen=True)
class PensionSpec:
    person_key: str
    start_year: int

    # 팀원이 계산한 2026년 가치 기준
    # 세전 월 국민연금 추정액
    monthly_gross_2026: int

    # 실제 엔진 연결용
    # {연도: 세후 명목 연금액}
    annual_net_nominal: Mapping[int, int] | None = None


PENSION_SPECS = (
    PensionSpec(
        person_key="a",
        start_year=2034,
        monthly_gross_2026=1_030_400,
    ),
    PensionSpec(
        person_key="spouse",
        start_year=2031,
        monthly_gross_2026=1_710_800,
    ),
)


def build_gross_pension_preview(
    specs=PENSION_SPECS,
    config=BASE_CONFIG,
):
    """
    세전 국민연금 예상액을 연도별로 미리 보여준다.

    2026년 가치 금액에 물가상승률 2.2% 적용.
    수급개시연도부터 12개월 수령한다고
    가정한 연 단위 참고용 계산.

    주의:
    세금, 재직자 노령연금 감액,
    실제 수급개시 월은 아직 미반영.
    엔진의 세후 pension_flows로 직접 사용 금지.
    """
    result = {}

    for spec in specs:
        if spec.monthly_gross_2026 < 0:
            raise ValueError(
                "국민연금 추정액은 음수일 수 없습니다."
            )

        for year in range(
            max(spec.start_year, config.start_year),
            config.end_year + 1,
        ):
            factor = (
                (1 + config.inflation_rate)
                ** (year - config.start_year)
            )

            annual_gross = round(
                spec.monthly_gross_2026
                * 12
                * factor
            )

            result[year] = (
                result.get(year, 0)
                + annual_gross
            )

    return result


def build_pension_flows(
    specs,
    config=BASE_CONFIG,
):
    """
    팀원 계산 결과를 기본 엔진에 연결한다.

    입력:
        PensionSpec.annual_net_nominal
        = {연도: 세후 명목 국민연금액}

    출력:
        {연도: 부부 합산 세후 명목 국민연금액}

    세후 금액이 없으면 오류를 발생시켜
    세전 연금액을 세후로 잘못 사용하는 것을 방지.
    """
    result = {}
    seen_keys = set()

    for spec in specs:
        if spec.person_key in seen_keys:
            raise ValueError(
                f"국민연금 대상자 중복: {spec.person_key}"
            )

        seen_keys.add(spec.person_key)

        if spec.annual_net_nominal is None:
            raise ValueError(
                f"{spec.person_key}: 세후 국민연금 "
                "계산 결과가 아직 없습니다."
            )

        schedule = spec.annual_net_nominal

        if not isinstance(schedule, Mapping):
            raise TypeError(
                "연금 일정은 연도별 금액 딕셔너리여야 합니다."
            )

        if (
            config.start_year <= spec.start_year
            <= config.end_year
            and spec.start_year not in schedule
        ):
            raise ValueError(
                f"{spec.person_key}: 수급개시연도 "
                f"{spec.start_year}년 금액이 누락되었습니다."
            )

        for year, amount in schedule.items():
            if not isinstance(year, int):
                raise TypeError("연도는 정수여야 합니다.")

            if year < spec.start_year:
                raise ValueError(
                    f"{spec.person_key}: 수급개시 전 "
                    "연금액이 입력되었습니다."
                )

            if (
                not isinstance(amount, int)
                or isinstance(amount, bool)
                or amount < 0
            ):
                raise ValueError(
                    "연금액은 0 이상의 정수 원화여야 합니다."
                )

            if config.start_year <= year <= config.end_year:
                result[year] = (
                    result.get(year, 0) + amount
                )

    return result
