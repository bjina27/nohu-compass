"""결정 변수 조합 비교 실행기 (A3).

상담 결정 변수(국민연금 개시나이 × 퇴직급여 방식 × 생활비 변경)의 조합마다
22개 투자전략 × 최소/계획 2장부를 같은 미래(같은 가구 seed·같은 시장 경로)로 계산해
조합·전략별 요약 지표를 낸다.

- 투자수익·비상자금 규칙은 팀원 goal_based_mc의 dynamic_return과 동일하다
  (portfolio_policy.target_weights + 반년복리 investment_return_fn).
- 가구 seed: base_seed + 1,000,000 + path_index, 시장 경로: generate_asset_returns(seed=base_seed) — 팀원과 동일.
- 조합 목록은 실행 전에 JSON으로 저장한다(사전 고정). 이 결과는 '탐색 단계'이며,
  상위 조합은 새 seed로 재확인한 뒤 팀원 선정 절차를 적용한다.
"""
from __future__ import annotations

import itertools
import math
import time
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

AGES = (90, 95, 100)
BIRTH_YEAR_A = 1969


def default_grid():
    """사전 제안 조합: 국민연금 3×3 × 퇴직급여 2 × 생활비 3 = 54."""
    claims = [(a, s) for a in (60, 65, 70) for s in (59, 64, 69)]
    retirements = [("lump_sum", "lump_sum", 20, 20), ("annuity", "annuity", 20, 20)]
    livings = [None, (2027, 2_658_000), (2036, 2_658_000)]
    grid = []
    for i, (c, r, l) in enumerate(itertools.product(claims, retirements, livings)):
        grid.append({
            "combo_id": f"C{i:02d}",
            "a_claim_age": c[0], "spouse_claim_age": c[1],
            "a_method": r[0], "spouse_method": r[1],
            "a_payout_years": r[2], "spouse_payout_years": r[3],
            "living_change_year": None if l is None else l[0],
            "monthly_living_after_change": None if l is None else l[1],
        })
    return grid


_W = {}


def _init(strategies, basis, years, min_policy, grid, market_paths, irp_rate):
    from config import BASE_CONFIG, HOUSEHOLD
    from full_simulation import _housing_flows, _retirement_flows, _year_end_lump_sums
    from scenarios import SCENARIOS
    cfgs, rets, yes = [], [], []
    for g in grid:
        cfg = BASE_CONFIG
        if g["living_change_year"] is not None:
            cfg = replace(BASE_CONFIG, living_cost_change_year=g["living_change_year"],
                          monthly_living_cost_after_change=g["monthly_living_after_change"])
        cfgs.append(cfg)
        key = (g["a_method"], g["spouse_method"], g["a_payout_years"], g["spouse_payout_years"])
        rets.append(dict(_retirement_flows(*key, irp_rate)))
        yes.append(dict(_year_end_lump_sums(*key)))
    _W.update(strategies=strategies, basis=basis, years=list(years),
              yidx={y: j for j, y in enumerate(years)}, min_policy=min_policy, grid=grid,
              market=market_paths, cfgs=cfgs, rets=rets, yes=yes,
              scenario=SCENARIOS["full"], household=HOUSEHOLD,
              housing=dict(_housing_flows(BASE_CONFIG)), nps_cache={},
              end_years={age: BIRTH_YEAR_A + age for age in AGES},
              infl2069=(1 + BASE_CONFIG.inflation_rate) ** (years[-1] - BASE_CONFIG.start_year),
              infl2059=(1 + BASE_CONFIG.inflation_rate) ** (BIRTH_YEAR_A + 90 - BASE_CONFIG.start_year))


def _nps(st, claim):
    from nps_net_adapter import build_nps_net_flows
    rkey = None if st is None else tuple((st[k]["success"], st[k]["duration_years"]) for k in ("a", "spouse"))
    key = (rkey, claim)
    if key not in _W["nps_cache"]:
        _W["nps_cache"][key] = build_nps_net_flows(
            scenario=_W["scenario"], household=_W["household"], reemployment_state=st,
            claim_ages={"a": claim[0], "spouse": claim[1]},
        ).household_net_nominal
    return _W["nps_cache"][key]


def _chunk(path_ids):
    """경로 묶음 처리 → 경로별 부족 여부·실질자산 + 합산 카운트."""
    from engine import simulate
    from reemployment_risk import sample_household_reemployment
    from simulation.portfolio_policy import target_weights
    G, S = len(_W["grid"]), len(_W["strategies"])
    n = len(path_ids)
    short = np.zeros((n, G, S, 2, len(AGES)), dtype=bool)        # 경로별 [ledger 0=min,1=plan][나이]
    unfunded_sum = np.zeros((G, S, 2), dtype=np.int64)
    child_miss = np.zeros((G, S), dtype=np.int64)
    child_due = np.zeros((G, S), dtype=np.int64)
    terminal_real = np.zeros((n, G, S))       # 계획장부 2069년(A씨 100세) 실질자산
    terminal_real_90 = np.zeros((n, G, S))    # 계획장부 2059년(A씨 90세) 실질자산
    invalid = np.zeros(G, dtype=bool)
    for pi, p in enumerate(path_ids):
        seed = _W["base_seed"] + 1_000_000 + p
        mpath = _W["market"][p]
        st = sample_household_reemployment(random_seed=seed) if _W["scenario"].reemployment else None
        for gi, g in enumerate(_W["grid"]):
            if invalid[gi]:
                continue
            try:
                nps = _nps(st, (g["a_claim_age"], g["spouse_claim_age"]))
            except ValueError:
                invalid[gi] = True
                continue
            for si, s in enumerate(_W["strategies"]):
                for li, mode in enumerate(("minimum", "plan")):
                    def rate(year, state, _s=s):
                        w = target_weights(
                            year=year, financial_assets=float(state["opening_assets"]),
                            emergency_months=int(_s["emergency_months"]),
                            equity_share_of_remainder=float(_s["equity_share_of_remainder"]),
                            basis=_W["basis"])
                        return float(np.dot(w, mpath[_W["yidx"][year]]))
                    rows = simulate(
                        scenario=_W["scenario"], config=_W["cfgs"][gi], household=_W["household"],
                        pension_flows=dict(nps), retirement_flows=dict(_W["rets"][gi]),
                        housing_costs=dict(_W["housing"]), investment_return_fn=rate,
                        spending_policy=_W["min_policy"] if mode == "minimum" else None,
                        year_end_inflows=dict(_W["yes"][gi]), random_seed=seed, reemployment_state=st)
                    first_short = next((r["year"] for r in rows if r["unfunded_amount"] > 1e-7), None)
                    for ai, age in enumerate(AGES):
                        if first_short is not None and first_short <= _W["end_years"][age]:
                            short[pi, gi, si, li, ai] = True
                    unfunded_sum[gi, si, li] += int(rows[-1]["cumulative_unfunded"])
                    if mode == "plan":
                        terminal_real[pi, gi, si] = rows[-1]["closing_assets"] / _W["infl2069"]
                        y90 = next(r for r in rows if r["year"] == _W["end_years"][90])
                        terminal_real_90[pi, gi, si] = y90["closing_assets"] / _W["infl2059"]
                        if any(r["son_target_one_time_support"] > 0 for r in rows):
                            child_due[gi, si] += 1
                        if any(r["son_support_capacity_shortfall"] > 0 for r in rows):
                            child_miss[gi, si] += 1
    return short, unfunded_sum, child_miss, child_due, terminal_real, terminal_real_90, invalid


def _init_with_seed(base_seed, *args):
    _init(*args)
    _W["base_seed"] = base_seed


def _wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / d
    return max(0.0, c - h), min(1.0, c + h)


def run_decision_grid(*, contract, market_json, n_paths, years, base_seed=20261114,
                      essential_family_support=(), grid=None, workers=15,
                      irp_rate=None, chunk_paths=20, progress=None, return_paths=False):
    from full_simulation import IRP_RETURN_RATE
    from simulation.market_paths import generate_asset_returns, load_market_assumptions
    from simulation.spending_policy import validate_spending_policy
    grid = grid or default_grid()
    irp_rate = IRP_RETURN_RATE if irp_rate is None else irp_rate
    strategies = contract["strategies"]
    basis = contract["emergency_fund_basis"]
    min_policy = validate_spending_policy({
        "mode": "minimum", "monthly_min_living_2026": float(basis["monthly_min_living_2026"]),
        "essential_family_support": tuple(essential_family_support)}, plan_monthly_living=1e100)
    market = load_market_assumptions(market_json)
    paths = generate_asset_returns(market, n_paths=n_paths, years=list(years), seed=base_seed)
    chunks = [list(range(i, min(i + chunk_paths, n_paths))) for i in range(0, n_paths, chunk_paths)]
    G, S = len(grid), len(strategies)
    short_paths = np.zeros((n_paths, G, S, 2, len(AGES)), dtype=bool)
    unfunded_sum = np.zeros((G, S, 2), dtype=np.int64)   # 정수 원화 합산 → 병렬·묶음 크기와 무관하게 동일
    child_miss = np.zeros((G, S), dtype=np.int64)
    child_due = np.zeros((G, S), dtype=np.int64)
    terminal = np.zeros((n_paths, G, S))
    terminal90 = np.zeros((n_paths, G, S))
    invalid = np.zeros(G, dtype=bool)
    t0 = time.time()
    with Pool(workers, initializer=_init_with_seed,
              initargs=(base_seed, strategies, basis, years, min_policy, grid, paths, irp_rate)) as pool:
        for done, (ids, res) in enumerate(zip(chunks, pool.imap(_chunk, chunks)), 1):
            a, b, c, d, e, e90, f = res
            sl = slice(ids[0], ids[-1] + 1)
            short_paths[sl] = a
            unfunded_sum += b; child_miss += c; child_due += d
            terminal[sl] = e
            terminal90[sl] = e90
            invalid |= f
            if progress:
                progress(min(done * chunk_paths, n_paths), n_paths, time.time() - t0)

    short = short_paths.sum(axis=0)
    rows = []
    for gi, g in enumerate(grid):
        for si, s in enumerate(strategies):
            row = {**g, "valid": not bool(invalid[gi]), "strategy": s["id"],
                   "emergency_months": s["emergency_months"],
                   "equity_share_of_remainder": s["equity_share_of_remainder"], "n_paths": n_paths}
            if invalid[gi]:
                rows.append(row)
                continue
            for li, led in enumerate(("minimum", "plan")):
                for ai, age in enumerate(AGES):
                    k = int(short[gi, si, li, ai])
                    lo, hi = _wilson(k, n_paths)
                    row[f"{led}_shortfall_count_{age}"] = k
                    row[f"{led}_shortfall_prob_{age}"] = k / n_paths
                    if age == 100:
                        row[f"{led}_shortfall_ci95_lo_100"] = lo
                        row[f"{led}_shortfall_ci95_hi_100"] = hi
                row[f"{led}_mean_cumulative_unfunded"] = unfunded_sum[gi, si, li] / n_paths
            t = np.sort(terminal[:, gi, si])
            t90 = np.sort(terminal90[:, gi, si])
            k5 = max(1, int(0.05 * n_paths))
            row.update({
                "plan_terminal_real_p05": float(np.quantile(t, 0.05)),
                "plan_terminal_real_p10": float(np.quantile(t, 0.10)),
                "plan_terminal_real_p50": float(np.quantile(t, 0.50)),
                "plan_terminal_real_p90": float(np.quantile(t, 0.90)),
                "plan_terminal_real_cvar05": float(t[:k5].mean()),
                "plan_real_p50_90": float(np.quantile(t90, 0.50)),
                "plan_real_cvar05_90": float(t90[:k5].mean()),
                "child_goal_due_count": int(child_due[gi, si]),
                "child_goal_miss_count": int(child_miss[gi, si]),
            })
            rows.append(row)
    out = {"grid": grid, "rows": rows, "elapsed_seconds": round(time.time() - t0, 1),
           "invalid_combos": [g["combo_id"] for gi, g in enumerate(grid) if invalid[gi]]}
    if return_paths:
        # 2단계 재확인용 경로별 결과: short[path, combo, strategy, ledger, age], 실질자산[path, combo, strategy]
        out["paths"] = {"short": short_paths, "terminal_real_100": terminal, "terminal_real_90": terminal90}
    return out
