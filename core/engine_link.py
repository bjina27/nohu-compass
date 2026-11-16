"""엔진 연결 — '우리 집이라면?' 계산.

두 갈래:
1) 사전 계산 조회: 연금 나이·퇴직급여 방식·투자전략·시장·(현행 생활비)는 본실험 1만 경로 결과(data/grid_lookup.json)를 그대로 쓴다.
2) 빠른 계산: 생활비 금액·자녀 지원 규모·생활비 가드레일을 바꾸면 엔진을 경로 수를 줄여(기본 1,000) 실시간으로 돌린다.
   추천안도 같은 경로 수·같은 난수(seed 20261114)로 함께 돌려 비교하므로, 차이는 조건 때문이지 경로 수 때문이 아니다.

엔진은 afpk_simulation/ (본실험과 같은 코드)를 그대로 부르고, 입력만 바꾼다(simulation.tornado._init 와 같은 방식).
"""
import json
import sys
import threading
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "afpk_simulation"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

SEED = 20261114
BASE_LIVING = 2_958_000            # 현행 월 생활비 (config.BASE_CONFIG)
RECOMMENDED = dict(a=70, s=69, method="lump_sum", strategy="B00", living=BASE_LIVING, child=1.0, guard=True)
CHILD_OPTS = {1.0: "통계 그대로", 0.0: "지원 안 함", 0.5: "절반 (×0.5)", 1.5: "1.5배"}
_LOCK = threading.Lock()           # 엔진 작업 공간(전역)을 여러 사용자가 동시에 쓰지 않도록


@lru_cache(maxsize=1)
def _lookup():
    return json.loads((ROOT / "data" / "grid_lookup.json").read_text(encoding="utf-8"))


def lookup(a, s, method, strategy, market):
    return _lookup().get(f"{market}|{a}|{s}|{method}|now|{strategy}")


def needs_quick(cond):
    """조회표에 없는 조건이면 빠른 계산이 필요하다."""
    return cond["living"] != BASE_LIVING or cond["child"] != 1.0 or cond["guard"]


def _run(a, s, method, strategy, living, child, guard, market, n_paths, progress=None):
    import numpy as np  # noqa: F401  (엔진 의존성 확인용)
    import simulation.stress_test as stx
    import simulation.tornado as tn
    from config import BASE_CONFIG, HOUSEHOLD
    from full_simulation import _housing_flows, _retirement_flows, _year_end_lump_sums
    from scenarios import SCENARIOS
    from simulation.integrated_monte_carlo import load_contract
    from simulation.spending_policy import validate_spending_policy
    import engine

    contract = load_contract(ENGINE / "outputs/portfolios/step4_strategies.json")
    strategies = [x for x in contract["strategies"] if x["id"] == strategy]
    years = list(range(BASE_CONFIG.start_year, BASE_CONFIG.end_year + 1))
    claim = {"a": a, "spouse": s}
    min_policy = validate_spending_policy({
        "mode": "minimum", "monthly_min_living_2026": float(contract["emergency_fund_basis"]["monthly_min_living_2026"]),
        "essential_family_support": ("a_mother", "spouse_mother")}, plan_monthly_living=1e100)

    cfg = replace(BASE_CONFIG, monthly_living_cost=int(living))
    sc = SCENARIOS["full"]
    if child != 1.0:
        sc = replace(sc, son_independence_support_amount_2024=round(sc.son_independence_support_amount_2024 * child),
                     son_marriage_support_brackets_2015=tn._scale_brackets(sc.son_marriage_support_brackets_2015, child))
    key = (method, method, 20, 20)
    stx._W.clear()
    stx._W.update(
        spec={"crash": False, "inflation": False, "family": False}, strategies=strategies,
        basis=dict(contract["emergency_fund_basis"]), years=years, year_index={y: j for j, y in enumerate(years)},
        min_policy=min_policy, scenario=sc, config=cfg, household=HOUSEHOLD, claim_ages=claim,
        retirement=dict(_retirement_flows(*key)), housing=dict(_housing_flows(cfg)), year_end=dict(_year_end_lump_sums(*key)),
        nps_cache={}, family=None, factor_end=engine.inflation_factor(years[-1], cfg), factor_90=engine.inflation_factor(1969 + 90, cfg),
        guardrails=stx.guardrails_for("living" if guard else "none", claim), nps_scale=1.0, reemployment_override=None)
    paths = tn._market_paths(ENGINE / contract["market_scenarios"][market]["file"], None, n_paths, years, SEED)
    recs = []
    for p in range(n_paths):
        recs.extend(stx._path_task((p, SEED + 1_000_000 + p, paths[p]))[1])
        if progress and p % 20 == 0:
            progress(p / n_paths)
    out = stx._summarize(recs, n_paths)
    out = out.get(strategy, out) if isinstance(out, dict) and strategy in out else out
    pl, mi = out["plan"], out["minimum"]
    return dict(p50=pl["terminal_real_p50"] / 1e8, cvar=pl["terminal_real_cvar05"] / 1e8, plan=pl["shortfall_prob_100"] * 100,
                mini=mi["shortfall_prob_100"] * 100, child=out.get("child_goal_miss_prob", 0) * 100,
                cut=out.get("living_cut_any_prob", 0) * 100, n=n_paths)


@st.cache_data(show_spinner=False, max_entries=64)
def quick(a, s, method, strategy, living, child, guard, market, n_paths=1000):
    with _LOCK:
        return _run(a, s, method, strategy, living, child, guard, market, n_paths)


def compute(cond, market, n_paths=1000):
    """(바꾼 조건 결과, 추천안 결과, 방식 설명)"""
    if not needs_quick(cond):
        mine = lookup(cond["a"], cond["s"], cond["method"], cond["strategy"], market)
        base = lookup(70, 69, "lump_sum", "B00", market)
        if mine is not None:
            return mine, base, "사전 계산 · 1만 경로 (본실험 결과)"
    args = lambda c: (c["a"], c["s"], c["method"], c["strategy"], c["living"], c["child"], c["guard"], market, n_paths)
    rec = dict(RECOMMENDED)
    return quick(*args(cond)), quick(*args(rec)), f"빠른 계산 · {n_paths:,}경로 (추천안도 같은 경로·같은 난수로 계산)"
