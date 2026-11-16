"""국민연금 세후 추정액 + 퇴직급여 계산기 -> AFPK 현금흐름 엔진.

기존 run_integrated.py, calculator_bridge.py, engine.py를 덮어쓰지 않는다.
국민연금 세액은 시나리오별 재취업 소득을 반영하여 별도로 계산한다.

실행:
  python run_nps_connected.py
  python run_nps_connected.py --with-housing
  python run_nps_connected.py --with-housing --a-method annuity --a-payout-years 20
"""
import argparse
import csv
from pathlib import Path

from calculator_bridge import compute_retirement_net_flows
from config import BASE_CONFIG
from engine import simulate
from reemployment_risk import sample_household_reemployment
from nps_net_adapter import build_nps_net_flows
from scenarios import SCENARIOS

ROOT = Path(__file__).resolve().parent


def _write_csv(rows, path):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run(
    a_method='lump_sum',
    spouse_method='lump_sum',
    a_payout_years=20,
    spouse_payout_years=20,
    with_housing=False,
    random_seed=20261114,
    out_root=None,
    claim_ages=None,
):
    retirement = compute_retirement_net_flows(
        a_method=a_method,
        spouse_method=spouse_method,
        a_payout_years=a_payout_years,
        spouse_payout_years=spouse_payout_years,
    )
    if with_housing:
        from interfaces.housing import build_housing_flows
        housing = build_housing_flows()
        housing_flows = housing.cashflows
        print(f'주택담보대출 상환 반영: 월 {housing.monthly_payment:,}원')
    else:
        housing_flows = None
        print('주택담보대출 미연결: --with-housing 옵션으로 연결 가능')

    a_tag = f'{a_method}_{a_payout_years}y' if a_method == 'annuity' else a_method
    spouse_tag = f'{spouse_method}_{spouse_payout_years}y' if spouse_method == 'annuity' else spouse_method
    # housing 포함/미포함 결과가 서로 덮어쓰지 않도록 폴더명에 housing 여부를 포함한다.
    housing_tag = 'housing' if with_housing else 'no_housing'
    base_root = ROOT / 'results' if out_root is None else Path(out_root)
    claim_ages = {k: v for k, v in (claim_ages or {}).items() if v is not None}
    # 국민연금 개시 나이를 바꾼 경우 폴더명에 표시해 정상수령 결과와 섞이지 않게 한다.
    claim_tag = ''.join(f'_nps{k}{v}' for k, v in sorted(claim_ages.items()))
    out_dir = base_root / 'nps_net_integration' / f'{a_tag}_{spouse_tag}_{housing_tag}{claim_tag}'
    for scenario_key, scenario in SCENARIOS.items():
        reemployment_state = (
            sample_household_reemployment(random_seed=random_seed)
            if scenario.reemployment else None
        )
        nps = build_nps_net_flows(
            scenario=scenario,
            config=BASE_CONFIG,
            reemployment_state=reemployment_state,
            claim_ages=claim_ages,
        )
        rows = simulate(
            scenario=scenario,
            pension_flows=nps.household_net_nominal,
            retirement_flows=retirement.net_annual_nominal,
            housing_costs=housing_flows,
            random_seed=random_seed,
            reemployment_state=reemployment_state,
        )
        # 외부 계산기 정책검증 및 주택/투자/가족지원 제한을 명시한다.
        for row in rows:
            row['nps_tax_assumption'] = nps.status
            row['final_projection_validated'] = False
        _write_csv(rows, out_dir / f'{scenario_key}.csv')
        _write_csv(nps.details, out_dir / f'{scenario_key}_nps_breakdown.csv')
        if scenario_key == 'base':
            print('국민연금 기본 시나리오 (2026년 가치 세전 월액)')
            for key, monthly in nps.gross_monthly_2026.items():
                info = nps.claim_info[key]
                start_year = info['claim_year']
                print(f'  {key}: 월 {monthly:,}원, {info["claim_type"]} {info["claim_age"]}세 '
                      f'(조정 {info["adjustment_rate"]:+.0%}), 수급개시 {start_year}년(6개월)')
                print(f'      첫해 명목 세후 {nps.by_person_net_nominal[key][start_year]:,}원')
            print('  66세 연말까지 기존 직장 급여 유지, 67세부터 재취업 가능: 엔진 규칙 적용')
    print('연도별 국민연금/퇴직급여 현금흐름 CSV 저장:', out_dir)
    print('주의: 2026년 제도·세법 고정 추정. 건강보험료·미확정 가족지원·투자/주택 기타비용 등은 별도입니다.')
    return out_dir


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--a-method', choices=['lump_sum', 'annuity'], default='lump_sum')
    parser.add_argument('--spouse-method', choices=['lump_sum', 'annuity'], default='lump_sum')
    parser.add_argument('--a-payout-years', type=int, default=20, help='A씨 IRP 연금 수령기간(년). annuity 선택 시 사용')
    parser.add_argument('--spouse-payout-years', type=int, default=20, help='배우자 IRP 연금 수령기간(년). annuity 선택 시 사용')
    parser.add_argument('--with-housing', action='store_true')
    parser.add_argument('--seed', type=int, default=20261114)
    parser.add_argument('--a-claim-age', type=int, default=None,
                        help='A씨 국민연금 개시 나이 (60~70, 기본 65=정상)')
    parser.add_argument('--spouse-claim-age', type=int, default=None,
                        help='배우자 국민연금 개시 나이 (59~69, 기본 64=정상)')
    args = parser.parse_args()
    run(
        a_method=args.a_method,
        spouse_method=args.spouse_method,
        a_payout_years=args.a_payout_years,
        spouse_payout_years=args.spouse_payout_years,
        with_housing=args.with_housing,
        random_seed=args.seed,
        claim_ages={'a': args.a_claim_age, 'spouse': args.spouse_claim_age},
    )
