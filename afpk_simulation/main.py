
import csv
from pathlib import Path

from config import (
    BASE_CONFIG,
    HOUSEHOLD,
)
from engine import (
    simulate,
    check_persona_2026,
)
from scenarios import SCENARIOS


# main.py가 있는 폴더를 기준으로 결과 저장
OUTPUT_DIR = (
    Path(__file__).resolve().parent / "results"
)


def save_csv(rows, filename):
    """시뮬레이션 결과를 CSV로 저장."""

    if not rows:
        raise ValueError(
            "저장할 시뮬레이션 결과가 없습니다."
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = OUTPUT_DIR / filename

    with path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=list(rows[0].keys()),
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"저장 완료: {path}")


def get_year(rows, year):
    """결과에서 특정 연도를 조회."""

    for row in rows:
        if row["year"] == year:
            return row

    raise ValueError(
        f"{year}년 결과를 찾을 수 없습니다."
    )


def unconfirmed_warnings(config):
    """legacy 실행 범위 및 임시 가정 안내."""

    warnings = [
        "[legacy] main.py는 국민연금·퇴직급여·주택비가 빠진 legacy projection입니다. "
        "최종 자산고갈 분석에 사용 금지.",
        "[최종 기준] full cashflow는 full_simulation.run_full_simulation()을 사용하세요.",
        "[확정] 가족지원 종료: 자녀 확률형 독립·결혼(44세까지) + "
        "자녀 정기지원 45세 cutoff + 부모 100세 cutoff",
        "[확정] 임금상승률 A씨 3.08%, 배우자 0.83% "
        "(KLoSA 동일인·동일직장 임금변화율 연환산 중앙값, 통계 기반 모델 적용값)",
        "[임시] 세금·사회보험료는 개인별 추정 차감률 사용(후속 정교화 과제)",
        "[미연결] 투자 모듈",
    ]

    return warnings


def run_all_scenarios(
    config=BASE_CONFIG,
    household=HOUSEHOLD,
    pension_flows=None,
    retirement_flows=None,
    housing_costs=None,
    investment_profits=None,
    random_seed=20261114,
):
    """모든 시나리오를 동일한 기본 엔진·동일 seed로 실행."""
    all_results = {}

    for key, scenario in SCENARIOS.items():
        rows = simulate(
            scenario=scenario,
            config=config,
            household=household,
            pension_flows=pension_flows,
            retirement_flows=retirement_flows,
            housing_costs=housing_costs,
            investment_profits=investment_profits,
            random_seed=random_seed,
        )
        all_results[key] = rows
        save_csv(rows, f"{key}.csv")

    return all_results


def verify_results(all_results):
    """현재 엔진 규칙의 핵심 회계·경계조건 검증."""
    check_persona_2026()

    base_2026 = get_year(all_results["base"], 2026)
    expected_2026 = {
        "gross_wage": 75_000_000,
        "tax_and_insurance": 9_286_000,
        "net_wage": 65_714_000,
        "living_cost": 35_496_000,
        "family_support": 8_289_000,
        "net_cashflow": 21_929_000,
        "closing_assets": 92_059_000,
    }
    for field, expected in expected_2026.items():
        actual = base_2026[field]
        if actual != expected:
            raise AssertionError(
                f"2026년 {field} 검증 실패: 기대 {expected:,}원, 실제 {actual:,}원"
            )

    if any(row["reemployment_wage"] != 0 for row in all_results["base"]):
        raise AssertionError("기본 시나리오에 재취업 소득이 있습니다.")

    # 66세 연말까지 기존 직장 급여 유지, 67세부터 0원.
    if get_year(all_results["base"], 2033)["spouse_regular_wage"] <= 0:
        raise AssertionError("배우자의 66세 연도 급여가 누락되었습니다.")
    if get_year(all_results["base"], 2034)["spouse_regular_wage"] != 0:
        raise AssertionError("배우자의 67세 이후 기존 직장 급여가 남아 있습니다.")
    if get_year(all_results["base"], 2035)["a_regular_wage"] <= 0:
        raise AssertionError("A씨의 66세 연도 급여가 누락되었습니다.")
    if get_year(all_results["base"], 2036)["a_regular_wage"] != 0:
        raise AssertionError("A씨의 67세 이후 기존 직장 급여가 남아 있습니다.")

    # 기본 시나리오에는 확률형 부모·자녀 사건이 없어야 함.
    if any(row["parent_event_cost"] != 0 for row in all_results["base"]):
        raise AssertionError("기본 시나리오에 노부모 사건비용이 포함되었습니다.")
    if any(row["son_actual_one_time_support"] != 0 for row in all_results["base"]):
        raise AssertionError("기본 시나리오에 자녀 일회성 이벤트지원이 포함되었습니다.")

    # 모든 시나리오·연도의 회계 항등식.
    for key, rows in all_results.items():
        for row in rows:
            left = (
                row["opening_assets"]
                + row["net_cashflow"]
                + row["investment_profit"]
                + row["unfunded_amount"]
            )
            if left != row["closing_assets"]:
                raise AssertionError(f"{key} / {row['year']}년 회계 항등식 오류")

            # 증여세는 자녀 부담 추정치이며 부모 가구 현금유출에 더하지 않음.
            if row["household_gift_tax_outflow"] != 0:
                raise AssertionError("증여세가 부모 가구 현금유출에 잘못 포함되었습니다.")

            # 자녀 실제지원은 통계상 목표와 지급능력 중 작은 값이어야 함.
            if row["son_actual_one_time_support"] > row["son_target_one_time_support"]:
                raise AssertionError("자녀지원액이 통계상 목표지원액을 초과했습니다.")
            if row["son_actual_one_time_support"] > row["son_available_support_capacity"]:
                raise AssertionError("자녀지원액이 가구 지급능력을 초과했습니다.")

    print("\n모든 기본 검증 통과!")

def print_reports(all_results):
    """핵심 결과를 터미널에 출력."""

    # ---------------------------
    # 2026년 기본 현금흐름
    # ---------------------------
    base_2026 = get_year(
        all_results["base"],
        2026,
    )

    print("\n[2026년 기본 현금흐름]")
    print("-" * 60)

    print(
        "세전 근로소득:",
        f'{base_2026["gross_wage"]:,}원',
    )

    print(
        "세금·사회보험료:",
        f'{base_2026["tax_and_insurance"]:,}원',
    )

    print(
        "세후 근로소득:",
        f'{base_2026["net_wage"]:,}원',
    )

    print(
        "연간 잉여:",
        f'{base_2026["net_cashflow"]:,}원',
    )

    print(
        "기말 금융자산:",
        f'{base_2026["closing_assets"]:,}원',
    )

    # ---------------------------
    # 2030년 부모 질병 시나리오
    # ---------------------------
    health_2030 = get_year(
        all_results["health"],
        2030,
    )

    base_2030 = get_year(
        all_results["base"],
        2030,
    )

    print("\n[2030년 부모 질병 시나리오]")
    print("-" * 60)

    print(
        "추가 의료비:",
        f'{health_2030["health_shock_cost"]:,}원',
    )

    print(
        "기본 대비 현금흐름 차이:",
        f'{health_2030["net_cashflow"] - base_2030["net_cashflow"]:,}원',
    )

    # ---------------------------
    # 2035년 재취업 시나리오
    # ---------------------------
    re_2035 = get_year(
        all_results["reemployment"],
        2035,
    )

    base_2035 = get_year(
        all_results["base"],
        2035,
    )

    print("\n[2035년 재취업 시나리오]")
    print("-" * 60)

    print(
        "재취업 세전소득:",
        f'{re_2035["reemployment_wage"]:,}원',
    )

    print(
        "기본 대비 현금흐름 개선:",
        f'{re_2035["net_cashflow"] - base_2035["net_cashflow"]:,}원',
    )

    # ---------------------------
    # 시나리오별 2035년 비교
    # ---------------------------
    print("\n[시나리오별 2035년 현금흐름]")
    print("-" * 60)

    for key, rows in all_results.items():
        row = get_year(rows, 2035)

        print(
            f'{row["scenario"]}: '
            f'연 순현금흐름 '
            f'{row["net_cashflow"] / 10000:,.1f}만원'
        )

    # ---------------------------
    # 모듈 연결 상태
    # ---------------------------
    print("\n[모듈 연결 상태]")
    print("-" * 60)

    for field in (
        "pension_status",
        "retirement_status",
        "housing_status",
        "investment_status",
        "family_support_status",
        "projection_status",
    ):
        print(
            f"{field}: {base_2026[field]}"
        )


def main():
    print("[AFPK 현금흐름 엔진 v1 - legacy projection / 최종 분석은 full_simulation.py]")

    print("\n[실행 범위 및 주의사항]")

    for warning in unconfirmed_warnings(
        BASE_CONFIG
    ):
        print(warning)

    all_results = run_all_scenarios()

    verify_results(all_results)

    print_reports(all_results)


if __name__ == "__main__":
    main()
