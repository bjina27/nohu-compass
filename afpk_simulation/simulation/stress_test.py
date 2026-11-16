"""확정 조합(C48)·비교 전략(B00, B40)에 대한 결정론적 충격 스트레스 테스트.

엔진 계산 로직은 바꾸지 않는다. 각 시나리오는 '입력'만 바꾼다.
  S0 기준     : 충격 없음 (4단계와 같은 seed·경로 — 재현 확인용)
  S1 은퇴 직후 폭락 : 2036년(A씨 은퇴 다음 해) 국내주식 연수익률 −54.54%를 모든 경로에 덮어씀.
                     채권·현금 손실 0 (risk_capacity.py KOSPI_GFC_2007_2008 가정과 동일).
                     근거: 코스피 2007-10-31 종가 2,064.85 → 2008-10-24 종가 938.75.
  S2 고물가 지속   : 2027~2031년 물가 연 5% (그 밖의 해 2.2%). 엔진·국민연금(물가연동)·최소장부
                     생활비·사건 금액이 같은 물가경로를 쓴다. 임금상승률·시장수익률은 그대로(명목 고정)
                     두므로 실질구매력이 깎이는 방향의 충격이다.
  S3 가족 사건 최악 : A씨 어머니 2027년 뇌졸중, 배우자 어머니 2028년 장기요양 인정,
                     아들 2031년 결혼(독립 없이) + 결혼지원 목표 = 통계 최상위 구간 1.2억(2015년 가격)의
                     2026년 가치, 두 사람 모두 재취업 없음. (event_overrides.py 사용)
  S4 복합          : S1 + S3

같은 seed(경로 p → 가계 seed base_seed+1_000_000+p, 시장 seed base_seed)를 써서 시나리오 간
차이는 충격만의 효과다(공통 난수).
"""
from __future__ import annotations

from multiprocessing import Pool

import numpy as np

CRASH_YEAR = 2036
CRASH_EQUITY_RETURN = 938.75 / 2064.85 - 1.0          # ≈ −0.5454
HIGH_INFLATION = {y: 0.05 for y in range(2027, 2032)}  # 2027~2031년 연 5%
MARRIAGE_SUPPORT_2015_TOP = 120_000_000                 # 결혼지원 최상위 구간 대표값(2015년 가격)

SCENARIOS = {
    "S0": {"label": "기준(충격 없음)", "crash": False, "inflation": False, "family": False},
    "S1": {"label": "은퇴 직후 폭락(2036 주식 -54.5%)", "crash": True, "inflation": False, "family": False},
    "S2": {"label": "고물가 지속(2027~2031 연 5%)", "crash": False, "inflation": True, "family": False},
    "S3": {"label": "가족 사건 최악 조합", "crash": False, "inflation": False, "family": True},
    "S4": {"label": "복합(S1+S3)", "crash": True, "inflation": False, "family": True},
    # 변형: 결혼을 2040년(아들 41세)으로 늦춰 월 정기지원이 더 오래 이어지고, 큰 지원이 은퇴 후에 나가게 함
    "S3b": {"label": "가족 사건 최악(결혼 2040)", "crash": False, "inflation": False, "family": True,
            "marriage_year": 2040},
    "S4b": {"label": "복합(S1+S3b)", "crash": True, "inflation": False, "family": True,
            "marriage_year": 2040},
}

GUARD_MODES = ("none", "bridge", "living", "both")
MIN_LIVING_MONTHLY_2026 = 2_166_000   # 최소 장부 생활비 = 규칙② 감축 하한


def guardrails_for(mode, claim_ages):
    """가드레일 모드 → engine.simulate(guardrails=...) 인자. none이면 None."""
    if mode not in GUARD_MODES:
        raise ValueError(f"가드레일 모드는 {GUARD_MODES} 중 하나")
    if mode == "none":
        return None
    bridge_end = max(1969 + claim_ages["a"], 1967 + claim_ages["spouse"])  # 두 연금 모두 개시되는 해
    g = {}
    if mode in ("bridge", "both"):
        g["bridge_reserve_until"] = bridge_end
    if mode in ("living", "both"):
        g.update(living_floor_monthly_2026=MIN_LIVING_MONTHLY_2026,
                 living_cut_years=2, living_restore_years=3)
    return g


_W = {}


# ---------------------------------------------------------------- 물가 경로 교체
def _make_inflation_factor(base_rate, start_year, end_year, overrides):
    cum, f = {start_year: 1.0}, 1.0
    for y in range(start_year + 1, end_year + 2):
        f *= 1.0 + overrides.get(y, base_rate)
        cum[y] = f

    def inflation_factor(year, config):
        if year <= config.start_year or year not in cum:
            return (1 + config.inflation_rate) ** (year - config.start_year)
        return cum[year]
    return inflation_factor


def install_stressed_inflation(config, overrides):
    """엔진·국민연금·사건지정·최소장부가 같은 연도별 물가경로를 쓰도록 교체한다(프로세스 단위)."""
    import engine
    import event_overrides
    import nps_net_adapter
    fn = _make_inflation_factor(config.inflation_rate, config.start_year, config.end_year, overrides)
    engine.inflation_factor = fn
    nps_net_adapter.inflation_factor = fn
    event_overrides.inflation_factor = fn
    original = engine.apply_spending_policy

    def apply_spending_policy(expenses, *, year, start_year, inflation_rate, policy):
        n = year - start_year
        eff = fn(year, config) ** (1.0 / n) - 1.0 if n > 0 else inflation_rate
        return original(expenses, year=year, start_year=start_year, inflation_rate=eff, policy=policy)

    engine.apply_spending_policy = apply_spending_policy
    return fn


# ---------------------------------------------------------------- 사건 지정
def family_overrides(config, scenario, marriage_year=2031):
    from engine import _marriage_support_2026
    marriage_2026 = _marriage_support_2026(MARRIAGE_SUPPORT_2015_TOP, config, scenario)
    return {
        "parent": {"a_mother_stroke_year": 2027, "spouse_mother_ltc_entry_year": 2028},
        "child": {"marriage_year": marriage_year, "marriage_support": marriage_2026, "amount_basis": "2026"},
        "reemployment": {"a_duration_years": 0, "spouse_duration_years": 0},
    }


# ---------------------------------------------------------------- 워커
def _init_worker(spec, strategies, basis, years, min_policy, claim_ages, a_method, spouse_method,
                 guard_mode="none"):
    from config import BASE_CONFIG, HOUSEHOLD
    from full_simulation import _retirement_flows, _housing_flows, _year_end_lump_sums
    from scenarios import SCENARIOS as ENGINE_SCENARIOS
    config = BASE_CONFIG
    sc = ENGINE_SCENARIOS["full"]
    infl = install_stressed_inflation(config, HIGH_INFLATION) if spec["inflation"] else None
    import engine
    key = (a_method, spouse_method, 20, 20)
    _W.update(
        spec=spec, strategies=strategies, basis=basis, years=list(years),
        year_index={y: j for j, y in enumerate(years)}, min_policy=min_policy,
        scenario=sc, config=config, household=HOUSEHOLD, claim_ages=claim_ages,
        retirement=dict(_retirement_flows(*key)), housing=dict(_housing_flows(config)),
        year_end=dict(_year_end_lump_sums(*key)), nps_cache={},
        family=(family_overrides(config, sc, spec.get("marriage_year", 2031))
                if spec["family"] else None),
        factor_end=(infl or engine.inflation_factor)(years[-1], config),
        factor_90=(infl or engine.inflation_factor)(1969 + 90, config),
        guardrails=guardrails_for(guard_mode, claim_ages),
    )


def _household(master_seed, rate_fn, spending_policy):
    from engine import simulate
    from nps_net_adapter import build_nps_net_flows
    from reemployment_risk import sample_household_reemployment
    from parent_risk import sample_parent_events
    from child_risk import sample_child_events
    from event_overrides import (apply_child_overrides, apply_parent_overrides,
                                 apply_reemployment_overrides)
    sc, cfg = _W["scenario"], _W["config"]
    st = sample_household_reemployment(random_seed=master_seed)
    parent_state = child_state = None
    if _W.get("reemployment_override"):          # 토네이도: 재취업 기간 고정
        st, sc = apply_reemployment_overrides(st, _W["reemployment_override"], sc)
    fam = _W["family"]
    if fam:
        st, sc = apply_reemployment_overrides(st, fam["reemployment"], sc)
        parent_state = apply_parent_overrides(
            sample_parent_events(scenario=sc, config=cfg, random_seed=master_seed),
            fam["parent"], cfg, sc)
        child_state = apply_child_overrides(
            sample_child_events(scenario=sc, config=cfg, random_seed=master_seed),
            fam["child"], cfg)
    key = tuple((st[k]["success"], st[k]["duration_years"]) for k in ("a", "spouse"))
    nps = _W["nps_cache"].get(key)
    if nps is None:
        nps = build_nps_net_flows(scenario=sc, config=cfg, household=_W["household"],
                                  reemployment_state=st,
                                  claim_ages=_W["claim_ages"]).household_net_nominal
        scale = _W.get("nps_scale", 1.0)          # 토네이도: 세후 국민연금 ±%
        if scale != 1.0:
            nps = {y: round(v * scale) for y, v in nps.items()}
        _W["nps_cache"][key] = nps
    return simulate(
        scenario=sc, config=cfg, household=_W["household"],
        pension_flows=dict(nps), retirement_flows=dict(_W["retirement"]),
        housing_costs=dict(_W["housing"]), investment_return_fn=rate_fn,
        spending_policy=spending_policy, year_end_inflows=dict(_W["year_end"]),
        random_seed=master_seed, reemployment_state=st,
        parent_event_state=parent_state, child_event_state=child_state,
        guardrails=_W.get("guardrails"),
    )


def _path_task(args):
    p, household_seed, market_path = args
    from simulation.portfolio_policy import target_weights
    from simulation.simulation_metrics import path_outcome
    out = []
    end_year = _W["years"][-1]
    for s in _W["strategies"]:
        rec = {"strategy": s["id"]}
        for mode in ("minimum", "plan"):
            def rate(year, state, _s=s):
                w = target_weights(
                    year=year, financial_assets=float(state["opening_assets"]),
                    emergency_months=int(_s["emergency_months"]),
                    equity_share_of_remainder=float(_s["equity_share_of_remainder"]),
                    basis=_W["basis"])
                return float(np.dot(w, market_path[_W["year_index"][year]]))
            rows = _household(household_seed, rate, _W["min_policy"] if mode == "minimum" else None)
            o100 = path_outcome(rows, end_year=end_year)
            o90 = path_outcome(rows, end_year=1969 + 90)
            rec[mode] = {
                "short100": o100["shortfall"], "short90": o90["shortfall"],
                "first": o100["first_shortfall_year"], "unfunded": o100["cumulative_unfunded"],
                "terminal_nominal": o100["terminal_assets"],
                "terminal_real": o100["terminal_assets"] / _W["factor_end"],
            }
            if mode == "plan":
                cut = [r for r in rows if r.get("guardrail_living_cut")]
                rec["cut_years"] = len(cut)
                rec["first_cut"] = cut[0]["year"] if cut else None
                rec["child_miss"] = any(float(r.get("son_support_capacity_shortfall", 0)) > 0 for r in rows)
                rec["child_paid_max"] = max(float(r.get("son_actual_one_time_support", 0) or 0) for r in rows) \
                    if rows and "son_actual_one_time_support" in rows[0] else None
        out.append(rec)
    return p, out


# ---------------------------------------------------------------- 실행·집계
def _summarize(records, n_paths):
    def pct(v):
        return float(np.mean(v)) if v else 0.0
    res = {}
    for mode in ("minimum", "plan"):
        short100 = [r[mode]["short100"] for r in records]
        short90 = [r[mode]["short90"] for r in records]
        firsts = sorted(r[mode]["first"] for r in records if r[mode]["first"] is not None)
        real = np.sort(np.array([r[mode]["terminal_real"] for r in records]))
        k = max(1, int(np.floor(0.05 * n_paths)))
        res[mode] = {
            "shortfall_count_100": int(sum(short100)),
            "shortfall_prob_100": pct(short100),
            "shortfall_prob_90": pct(short90),
            "first_shortfall_year_median": (firsts[len(firsts) // 2] if firsts else None),
            "first_shortfall_year_earliest": (firsts[0] if firsts else None),
            "mean_cumulative_unfunded": float(np.mean([r[mode]["unfunded"] for r in records])),
            "terminal_real_p50": float(np.median(real)),
            "terminal_real_p05": float(real[k - 1]),
            "terminal_real_cvar05": float(real[:k].mean()),
            "terminal_nominal_p50": float(np.median([r[mode]["terminal_nominal"] for r in records])),
        }
    res["child_goal_miss_prob"] = pct([r["child_miss"] for r in records])
    cuts = [r.get("cut_years", 0) for r in records]
    res["living_cut_any_prob"] = pct([c > 0 for c in cuts])
    res["living_cut_years_mean"] = float(np.mean(cuts))
    res["living_cut_years_mean_if_cut"] = float(np.mean([c for c in cuts if c > 0])) if any(cuts) else 0.0
    paid = [r["child_paid_max"] for r in records if r.get("child_paid_max") is not None]
    res["child_one_time_paid_mean_nominal"] = float(np.mean(paid)) if paid else None
    return res


def run_scenario(*, scenario_id, contract, market_json, strategy_ids, n_paths, years,
                 base_seed, essential_family_support, claim_ages, a_method, spouse_method,
                 workers=15, chunksize=4, progress=None, guard_mode="none"):
    from simulation.market_paths import generate_asset_returns, load_market_assumptions
    from simulation.spending_policy import validate_spending_policy
    spec = SCENARIOS[scenario_id]
    strategies = [s for s in contract["strategies"] if s["id"] in strategy_ids]
    if len(strategies) != len(strategy_ids):
        raise ValueError(f"알 수 없는 전략: {strategy_ids}")
    min_policy = validate_spending_policy({
        "mode": "minimum",
        "monthly_min_living_2026": float(contract["emergency_fund_basis"]["monthly_min_living_2026"]),
        "essential_family_support": tuple(essential_family_support),
    }, plan_monthly_living=1e100)
    market = load_market_assumptions(market_json)
    paths = generate_asset_returns(market, n_paths=n_paths, years=years, seed=base_seed)
    if spec["crash"]:
        eq = list(market.assets).index("equity_kr")
        paths[:, list(years).index(CRASH_YEAR), eq] = CRASH_EQUITY_RETURN
    tasks = ((p, base_seed + 1_000_000 + p, paths[p]) for p in range(n_paths))
    per_strategy = {s["id"]: [] for s in strategies}
    with Pool(workers, initializer=_init_worker,
              initargs=(spec, strategies, contract["emergency_fund_basis"], years, min_policy,
                        claim_ages, a_method, spouse_method, guard_mode)) as pool:
        for done, (p, recs) in enumerate(pool.imap(_path_task, tasks, chunksize=chunksize), 1):
            for rec in recs:
                per_strategy[rec["strategy"]].append(rec)
            if progress and (done % max(n_paths // 10, 1) == 0 or done == n_paths):
                progress(done, n_paths)
    return {sid: _summarize(recs, n_paths) for sid, recs in per_strategy.items()}
