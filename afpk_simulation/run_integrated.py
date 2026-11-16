"""기존 main.py를 건드리지 않고 실제 계산기 연결 여부를 확인하는 실행 파일.

일시금/IRP는 팀원 입력 세금 추정을 반영한 세후 금액으로 엔진 연결.
국민연금은 기본 모드에서 세전 결과만 미리 보고, 엔진에는 넣지 않음.
국민연금까지 연결하려면 --nps-net-json으로 검증된 세후 일정을 전달하거나
--preview-untaxed-nps 옵션을 명시하여 '세금 미반영 임시' 시뮬레이션 실행.
"""
import argparse
import csv
import json
from pathlib import Path

from engine import simulate
from scenarios import SCENARIOS
from calculator_bridge import (
    compute_nps_gross_preview,
    compute_retirement_net_flows,
    net_pension_flows_from_verified_schedules,
)

ROOT = Path(__file__).resolve().parent


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(a_method='lump_sum', spouse_method='lump_sum',
        a_payout_years=20, spouse_payout_years=20,
        preview_untaxed_nps=False, nps_net_json=None):
    if preview_untaxed_nps and nps_net_json:
        raise ValueError('세후 일정과 세금 미반영 미리보기를 동시에 지정할 수 없습니다')
    nps = compute_nps_gross_preview()
    retirement = compute_retirement_net_flows(
        a_method=a_method, spouse_method=spouse_method,
        a_payout_years=a_payout_years, spouse_payout_years=spouse_payout_years,
    )
    print('팀원 국민연금 계산기 실행 결과 (2026년 가치, 세전)')
    for k, amount in nps.gross_monthly_2026.items():
        print(f'  {k}: 월 {amount:,}원 / B값 {nps.b_values[k]:,.0f}원')
    print('팀원 IRP 계산기 연결 결과 (세후 추정, 원)')
    for k, schedule in retirement.by_person_net.items():
        print(f'  {k}: {retirement.methods[k]} 첫 수령 {next(iter(schedule))}년 {next(iter(schedule.values())):,}원')

    if nps_net_json:
        with open(nps_net_json, encoding='utf-8') as f:
            raw = json.load(f)
        parsed = {key: {int(year): amount for year, amount in sched.items()}
                  for key, sched in raw.items()}
        pension_flows = net_pension_flows_from_verified_schedules(parsed)
        tag = 'verified_net'
        print('국민연금: 세후 일정 입력으로 엔진에 연결')
    elif preview_untaxed_nps:
        pension_flows = nps.gross_annual_nominal
        tag = 'UNVERIFIED_nps_gross_as_net_preview'
        print('*** 경고: 국민연금은 세전액을 세후액처럼 간주한 임시 비교용 결과입니다. ***')
        print('*** 재직자 감액, 세금, 지급개시월, 건강보험료 미반영. 최종 자산전망에 사용 금지. ***')
    else:
        pension_flows = None
        tag = 'retirement_only_nps_gross_separate'
        print('국민연금: 계산은 완료, 세후 미산정으로 엔진 유입액에서는 제외')

    out_dir = ROOT / 'results' / 'calculator_integration' / tag
    # 국민연금 세전 참고 계산표는 어떤 모드에서도 보존
    write_csv(
        [{'year':y,'nps_gross_annual_nominal':v,
          'nps_gross_a':nps.by_person_gross['a'].get(y,0),
          'nps_gross_spouse':nps.by_person_gross['spouse'].get(y,0),
          'tax_status':'세전 참고용'}
         for y,v in sorted(nps.gross_annual_nominal.items())],
        out_dir/'nps_gross_reference.csv'
    )
    # IRP 잔액은 현금흐름과 별도 저장. 합산해서 투자손익으로 넣지 말 것.
    balance_years = sorted(set().union(*(s.keys() for s in retirement.irp_balance_by_person.values())))
    if balance_years:
        write_csv(
            [{'year':y,
              'a_irp_closing':retirement.irp_balance_by_person['a'].get(y,0),
              'spouse_irp_closing':retirement.irp_balance_by_person['spouse'].get(y,0)}
             for y in balance_years],
            out_dir/'irp_balances_separate.csv'
        )
    outputs={}
    for key, scenario in SCENARIOS.items():
        rows=simulate(scenario=scenario,
                      pension_flows=pension_flows,
                      retirement_flows=retirement.net_annual_nominal)
        annotated=[{**r,'nps_calculation_status':('세후 일정 제공' if nps_net_json else
                         '세금 미반영 임시 미리보기' if preview_untaxed_nps else '세전만 계산, 세후 미연결'),
                    'retirement_calculation_status':'팀원 IRP/퇴직소득세 추정 반영'} for r in rows]
        write_csv(annotated,out_dir/f'{key}.csv')
        outputs[key]=annotated
    print('CSV 저장:',out_dir)
    if not preview_untaxed_nps and not nps_net_json:
        print('현재 CSV의 국민연금 유입은 미연결이므로 생애 자산잔액은 최종 결과가 아닙니다.')
    return outputs


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--a-method',choices=['lump_sum','annuity'],default='lump_sum')
    parser.add_argument('--spouse-method',choices=['lump_sum','annuity'],default='lump_sum')
    parser.add_argument('--a-payout-years',type=int,default=20,help='A씨 IRP 연금 수령기간(년). annuity 선택 시 사용')
    parser.add_argument('--spouse-payout-years',type=int,default=20,help='배우자 IRP 연금 수령기간(년). annuity 선택 시 사용')
    parser.add_argument('--preview-untaxed-nps',action='store_true')
    parser.add_argument('--nps-net-json',type=Path)
    args=parser.parse_args()
    run(a_method=args.a_method,spouse_method=args.spouse_method,
        a_payout_years=args.a_payout_years,spouse_payout_years=args.spouse_payout_years,
        preview_untaxed_nps=args.preview_untaxed_nps,nps_net_json=args.nps_net_json)
