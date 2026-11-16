"""KLoSA Beta-Binomial 재취업 이벤트 몬테카를로 요약 실행기.

[용도 제한] 재취업 모듈 검증용(test-only)이다. 최종 Monte Carlo가 아니다.
- 국민연금·퇴직급여·주택비가 연결되지 않은 legacy cashflow를 반복하므로
  '마지막연도 금융자산'과 고갈 관련 수치를 최종 자산고갈 분석에 사용하면 안 된다.
- 최종 Monte Carlo는 full_simulation.run_full_simulation()을 path마다 호출한다.
"""
import argparse
import statistics

from engine import simulate
from scenarios import SCENARIOS


def run(n=1000, seed=20261114):
    scenario = SCENARIOS["reemployment"]
    outcomes = []

    for i in range(n):
        rows = simulate(scenario=scenario, random_seed=seed + i)
        first = rows[0]
        last = rows[-1]
        outcomes.append({
            "a_success": bool(first["a_reemployment_success"]),
            "spouse_success": bool(first["spouse_reemployment_success"]),
            "a_duration": int(first["a_reemployment_duration_years"]),
            "spouse_duration": int(first["spouse_reemployment_duration_years"]),
            "closing_assets": last["closing_assets"],
            "cumulative_unfunded": last["cumulative_unfunded"],
        })

    def rate(key):
        return sum(x[key] for x in outcomes) / n

    print("[재취업 모듈 검증용 / 최종 자산고갈 분석 사용 금지]")
    print(f"시뮬레이션 n={n:,}")
    print(f"A씨 재취업 발생 비율: {rate('a_success'):.3%}")
    print(f"배우자 재취업 발생 비율: {rate('spouse_success'):.3%}")
    print("A씨 재취업기간 평균(전체 시행, 0 포함):", round(statistics.mean(x['a_duration'] for x in outcomes), 3))
    print("배우자 재취업기간 평균(전체 시행, 0 포함):", round(statistics.mean(x['spouse_duration'] for x in outcomes), 3))
    print("마지막연도 금융자산 중앙값:", round(statistics.median(x['closing_assets'] for x in outcomes)))
    return outcomes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20261114)
    args = parser.parse_args()
    run(n=args.n, seed=args.seed)
