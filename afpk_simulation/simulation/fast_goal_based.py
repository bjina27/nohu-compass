"""goal_based_mc.run_goal_based_mc()의 고속 실행 래퍼 (결과 동일).

원리
1) 가계 엔진 호출(경로 × 22전략 × 2장부)을 경로 단위로 여러 프로세스에서 병렬 계산한다.
   국민연금 세후 흐름은 재취업 상태(성공여부·지속기간)에만 의존하므로 조합별 1회만 계산해 캐시한다.
   퇴직급여·주택 흐름도 run_full_simulation과 같은 캐시 함수를 쓴다.
2) 팀원의 원본 run_goal_based_mc()를 그대로 호출하되, household_runner 자리에
   '미리 계산된 결과를 원래 호출 순서대로 돌려주는 replay 함수'를 넣는다.
   replay 함수는 원본 dynamic_return 콜백을 연도 순서대로 다시 호출하므로
   변동성 누적(vol_sum) 등 원본의 부수효과도 동일한 순서로 재현된다.
→ 집계·통계검정·전략선정·출력 형식은 원본 코드가 그대로 수행한다.

검증: scripts/verify_fast_goal_based.py (원본 순차 실행과 JSON 출력 비교)
"""
from __future__ import annotations

from multiprocessing import Pool

import numpy as np

KEEP = ("year", "unfunded_amount", "closing_assets",
        "son_target_one_time_support", "son_support_capacity_shortfall")

_W = {}


# household_runner가 functools.partial(run_full_simulation, ...)이면 그 인자를 그대로 따른다.
SUPPORTED_DECISIONS = {"claim_ages", "a_method", "spouse_method", "a_payout_years",
                       "spouse_payout_years", "config"}


def _decisions_from_runner(runner):
    import functools
    if isinstance(runner, functools.partial):
        kw = dict(runner.keywords)
        unknown = set(kw) - SUPPORTED_DECISIONS
        if unknown:
            raise ValueError(f"고속 실행기가 지원하지 않는 household_runner 인자: {sorted(unknown)}")
        return kw
    return {}


def _init_worker(strategies, basis, years, min_policy, decisions=None):
    from config import BASE_CONFIG, HOUSEHOLD
    from full_simulation import _retirement_flows, _housing_flows, _year_end_lump_sums
    from scenarios import SCENARIOS
    d = dict(decisions or {})
    config = d.get("config", BASE_CONFIG)
    key = (d.get("a_method", "lump_sum"), d.get("spouse_method", "lump_sum"),
           d.get("a_payout_years", 20), d.get("spouse_payout_years", 20))
    _W.update(
        strategies=strategies, basis=basis, years=list(years),
        year_index={y: j for j, y in enumerate(years)}, min_policy=min_policy,
        scenario=SCENARIOS["full"], config=config, household=HOUSEHOLD,
        retirement=dict(_retirement_flows(*key)),
        housing=dict(_housing_flows(config)), nps_cache={},
        year_end=dict(_year_end_lump_sums(*key)),
        claim_ages=d.get("claim_ages"),
    )


def _household(master_seed, investment_return_fn, spending_policy):
    """run_full_simulation(master_seed, investment_return_fn, spending_policy) 기본 인자와 동일 계산."""
    from engine import simulate
    from nps_net_adapter import build_nps_net_flows
    from reemployment_risk import sample_household_reemployment
    sc = _W["scenario"]
    st = sample_household_reemployment(random_seed=master_seed) if sc.reemployment else None
    key = None if st is None else tuple(
        (st[k]["success"], st[k]["duration_years"]) for k in ("a", "spouse"))
    nps = _W["nps_cache"].get(key)
    if nps is None:
        nps = build_nps_net_flows(scenario=sc, config=_W["config"], household=_W["household"],
                                  reemployment_state=st,
                                  claim_ages=_W["claim_ages"]).household_net_nominal
        _W["nps_cache"][key] = nps
    return simulate(
        scenario=sc, config=_W["config"], household=_W["household"],
        pension_flows=dict(nps), retirement_flows=dict(_W["retirement"]),
        housing_costs=dict(_W["housing"]),
        investment_return_fn=investment_return_fn, spending_policy=spending_policy,
        year_end_inflows=dict(_W["year_end"]),
        random_seed=master_seed, reemployment_state=st,
    )


def _path_task(args):
    """한 경로의 22전략 × (minimum, plan) 결과를 원본 호출 순서대로 반환."""
    p, household_seed, market_path = args
    from simulation.portfolio_policy import target_weights
    out = []
    for s in _W["strategies"]:
        for mode in ("minimum", "plan"):
            openings = []

            def rate(year, state, _s=s):
                openings.append((year, state["opening_assets"]))
                w = target_weights(
                    year=year, financial_assets=float(state["opening_assets"]),
                    emergency_months=int(_s["emergency_months"]),
                    equity_share_of_remainder=float(_s["equity_share_of_remainder"]),
                    basis=_W["basis"],
                )
                return float(np.dot(w, market_path[_W["year_index"][year]]))

            rows = _household(household_seed, rate,
                              _W["min_policy"] if mode == "minimum" else None)
            slim = [{k: r[k] for k in KEEP} for r in rows]
            out.append((household_seed, mode, slim, openings))
    return p, out


def run_goal_based_mc_fast(*, workers: int = 15, chunksize: int = 4, **kwargs) -> dict:
    """run_goal_based_mc와 같은 인자를 받고 같은 결과를 반환한다 (household_runner는 무시)."""
    from simulation.goal_based_mc import run_goal_based_mc
    from simulation.market_paths import generate_asset_returns, load_market_assumptions
    from simulation.spending_policy import validate_spending_policy

    contract = kwargs["contract"]
    n_paths = kwargs["n_paths"]
    years = list(kwargs["years"])
    base_seed = kwargs.get("base_seed", 20261114)
    min_policy = validate_spending_policy({
        "mode": "minimum",
        "monthly_min_living_2026": float(contract["emergency_fund_basis"]["monthly_min_living_2026"]),
        "essential_family_support": tuple(kwargs.get("essential_family_support", ())),
    }, plan_monthly_living=1e100)
    market = load_market_assumptions(kwargs["market_json"])
    paths = generate_asset_returns(market, n_paths=n_paths, years=years, seed=base_seed)
    tasks = ((p, base_seed + 1_000_000 + p, paths[p]) for p in range(n_paths))

    pool = Pool(workers, initializer=_init_worker,
                initargs=(contract["strategies"], contract["emergency_fund_basis"], years, min_policy,
                          _decisions_from_runner(kwargs.get("household_runner"))))
    try:
        stream = pool.imap(_path_task, tasks, chunksize=chunksize)

        def calls():
            expect = 0
            for p, items in stream:
                if p != expect:
                    raise RuntimeError("path order mismatch")
                expect += 1
                yield from items

        it = calls()

        def replay_runner(*, master_seed, investment_return_fn, spending_policy):
            seed, mode, slim, openings = next(it)
            want = "plan" if spending_policy is None else "minimum"
            if seed != master_seed or mode != want:
                raise RuntimeError(f"replay mismatch: {seed}/{mode} vs {master_seed}/{want}")
            for year, opening in openings:          # 원본 콜백 부수효과(변동성 누적) 재현
                investment_return_fn(year, {"opening_assets": opening})
            return [dict(r) for r in slim]

        kwargs = dict(kwargs, household_runner=replay_runner)
        result = run_goal_based_mc(**kwargs)
        try:
            next(it)
            raise RuntimeError("unused precomputed results")
        except StopIteration:
            pass
        return result
    finally:
        pool.terminate()
        pool.join()
