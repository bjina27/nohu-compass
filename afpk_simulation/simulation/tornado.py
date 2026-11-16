"""토네이도(일원) 민감도 분석.

가정 하나만 낮은 값/높은 값으로 바꾸고 나머지는 기준값으로 고정한다. 같은 seed(공통 난수)를 쓴다.
계산부는 simulation/stress_test.py의 워커를 그대로 쓰고, 이 모듈은 '입력 바꾸기'만 담당한다.

가정과 범위 (근거 구분: 통계·정책·가정·극단값)
  bond        채권 기대수익률(단순수익률) -1%p / +1%p                         가정
  inflation   물가상승률(전 기간) 1.5% / 3.0%, 명목 기대수익률도 같은 비율로 이동(피셔)  정책목표(2%) 기반
  living      계획 생활비 월 -30만 / +30만 원                                   조합비교와 같은 폭
  nps         세후 국민연금 -10% / +10%                                        정책 위험 가정
  wage        두 사람 임금상승률 -1%p / +1%p (퇴직 일시금은 최종임금 비율로 비례 조정 근사,
              국민연금 가입이력은 고정)                                          가정
  assets0     초기 금융자산 -20% / +20%                                          가정
  reemp       재취업: 둘 다 없음 / 둘 다 4년                                      극단값
  parent_prob 부모 사건 확률(뇌졸중·장기요양) ×0.5 / ×2                           가정
  parent_cost 부모 사건 비용 ×0.5 / ×2                                            가정
  child_amt   자녀 일회성 지원금(독립·결혼 대표금액) ×0.5 / ×1.5                    가정
퇴직 연령은 제외: 퇴직급여·국민연금 쪽 퇴직 연도가 고정이라 일관되게 바꿀 수 없다.
"""
from __future__ import annotations

import math
from dataclasses import replace
from multiprocessing import Pool

import numpy as np

BASE_INFLATION = 0.022

PARAMS = [
    # key, 이름, 낮은 값 라벨, 높은 값 라벨, 근거, 낮은 값, 높은 값
    ("bond", "채권 기대수익률", "-1%p", "+1%p", "가정", -0.01, 0.01),
    ("inflation", "물가상승률(금리 동반)", "1.5%", "3.0%", "정책목표 기반", 0.015, 0.030),
    ("living", "계획 생활비", "월 -30만", "월 +30만", "조합비교 폭", -300_000, 300_000),
    ("nps", "국민연금 급여", "-10%", "+10%", "정책 위험 가정", 0.9, 1.1),
    ("wage", "임금상승률", "-1%p", "+1%p", "가정(퇴직금 비례 근사)", -0.01, 0.01),
    ("assets0", "초기 금융자산", "-20%", "+20%", "가정", 0.8, 1.2),
    ("reemp", "재취업", "둘 다 없음", "둘 다 4년", "극단값", 0, 4),
    ("parent_prob", "부모 사건 확률", "×0.5", "×2", "가정", 0.5, 2.0),
    ("parent_cost", "부모 사건 비용", "×0.5", "×2", "가정", 0.5, 2.0),
    ("child_amt", "자녀 일회성 지원금", "×0.5", "×1.5", "가정", 0.5, 1.5),
]
PARAM_INDEX = {p[0]: p for p in PARAMS}


def _scale_brackets(brackets, k):
    return tuple({**b, "representative_amount": round(b["representative_amount"] * k)} for b in brackets)


def _init(variant, strategies, basis, years, min_policy, claim_ages, guard_mode):
    """워커 초기화: 기준 입력에 variant 하나만 적용해 stress_test._W를 채운다."""
    import engine
    import simulation.stress_test as st
    from config import BASE_CONFIG, HOUSEHOLD
    from full_simulation import _retirement_flows, _housing_flows, _year_end_lump_sums
    from scenarios import SCENARIOS

    cfg, hh, sc = BASE_CONFIG, HOUSEHOLD, SCENARIOS["full"]
    basis = dict(basis)
    key, val = variant if variant else (None, None)
    infl = None
    if key == "living":
        cfg = replace(cfg, monthly_living_cost=cfg.monthly_living_cost + val)
    elif key == "assets0":
        cfg = replace(cfg, initial_financial_assets=round(cfg.initial_financial_assets * val))
    elif key == "wage":
        hh = tuple(replace(p, wage_growth_rate=p.wage_growth_rate + val) for p in hh)
    elif key == "parent_prob":
        sc = replace(sc,
                     a_mother_stroke_annual_probability=min(1.0, sc.a_mother_stroke_annual_probability * val),
                     spouse_mother_ltc_probability_83_84=min(1.0, sc.spouse_mother_ltc_probability_83_84 * val),
                     spouse_mother_ltc_probability_85plus=min(1.0, sc.spouse_mother_ltc_probability_85plus * val))
    elif key == "parent_cost":
        sc = replace(sc, a_mother_stroke_cost_2026=round(sc.a_mother_stroke_cost_2026 * val),
                     spouse_mother_ltc_annual_cost_2026=round(sc.spouse_mother_ltc_annual_cost_2026 * val))
    elif key == "child_amt":
        sc = replace(sc,
                     son_independence_support_amount_2024=round(sc.son_independence_support_amount_2024 * val),
                     son_marriage_support_brackets_2015=_scale_brackets(sc.son_marriage_support_brackets_2015, val))
    elif key == "inflation":
        infl = st.install_stressed_inflation(cfg, {y: val for y in range(cfg.start_year + 1, cfg.end_year + 2)})
        basis["inflation_rate"] = val    # 비상자금 목표액도 같은 물가로

    rkey = ("lump_sum", "lump_sum", 20, 20)
    retirement = dict(_retirement_flows(*rkey))
    year_end = dict(_year_end_lump_sums(*rkey))
    if key == "wage":
        # 퇴직 일시금 ∝ 최종임금: (1+g+Δ)^n / (1+g)^n, n = 퇴직연도 - 2026
        for person, year in ((hh[0], 2035), (hh[1], 2033)):
            g0 = person.wage_growth_rate - val
            ratio = ((1 + g0 + val) / (1 + g0)) ** (year - cfg.start_year)
            for d in (retirement, year_end):
                if year in d:
                    d[year] = round(d[year] * ratio)

    st._W.clear()
    st._W.update(
        spec={"crash": False, "inflation": key == "inflation", "family": False},
        strategies=strategies, basis=basis, years=list(years),
        year_index={y: j for j, y in enumerate(years)}, min_policy=min_policy,
        scenario=sc, config=cfg, household=hh, claim_ages=claim_ages,
        retirement=retirement, housing=dict(_housing_flows(cfg)), year_end=year_end, nps_cache={},
        family=None,
        factor_end=(infl or engine.inflation_factor)(years[-1], cfg),
        factor_90=(infl or engine.inflation_factor)(1969 + 90, cfg),
        guardrails=st.guardrails_for(guard_mode, claim_ages),
        nps_scale=(val if key == "nps" else 1.0),
        reemployment_override=({"a_duration_years": val, "spouse_duration_years": val}
                               if key == "reemp" else None),
    )


def _market_paths(market_json, variant, n_paths, years, seed):
    from simulation.market_paths import MarketAssumptions, generate_asset_returns, load_market_assumptions
    m = load_market_assumptions(market_json)
    means = m.annual_log_means.copy()
    key, val = variant if variant else (None, None)
    if key == "bond":
        i = list(m.assets).index("bond_kr")
        mu = math.exp(means[i] + 0.5 * m.annual_log_cov[i, i]) - 1
        means[i] += math.log((1 + mu + val) / (1 + mu))
    elif key == "inflation":
        means = means + math.log((1 + val) / (1 + BASE_INFLATION))   # 피셔: 명목 = (1+실질)(1+물가)
    return generate_asset_returns(MarketAssumptions(m.assets, means, m.annual_log_cov, m.as_of),
                                  n_paths=n_paths, years=years, seed=seed)


def run_variant(*, variant, contract, market_json, strategy_id, n_paths, years, base_seed,
                essential_family_support, claim_ages, guard_mode, workers=15, chunksize=4):
    import simulation.stress_test as st
    from simulation.spending_policy import validate_spending_policy
    strategies = [s for s in contract["strategies"] if s["id"] == strategy_id]
    if len(strategies) != 1:
        raise ValueError(strategy_id)
    min_policy = validate_spending_policy({
        "mode": "minimum",
        "monthly_min_living_2026": float(contract["emergency_fund_basis"]["monthly_min_living_2026"]),
        "essential_family_support": tuple(essential_family_support)}, plan_monthly_living=1e100)
    paths = _market_paths(market_json, variant, n_paths, years, base_seed)
    tasks = ((p, base_seed + 1_000_000 + p, paths[p]) for p in range(n_paths))
    recs = []
    with Pool(workers, initializer=_init,
              initargs=(variant, strategies, contract["emergency_fund_basis"], years, min_policy,
                        claim_ages, guard_mode)) as pool:
        for _, out in pool.imap(st._path_task, tasks, chunksize=chunksize):
            recs.extend(out)
    return st._summarize(recs, n_paths)
