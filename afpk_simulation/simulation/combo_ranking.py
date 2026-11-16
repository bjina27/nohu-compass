"""결정 변수 조합 순위·생활비 민감도·재확인 통계 (팀 합의 2026-11-16, 결과 보기 전 고정).

순위 규칙
- 순위 대상: 현행 생활비 조합(국민연금 개시나이 × 퇴직급여 방식). 생활비 변경은 순위에서 제외하고 민감도로 따로 표시.
- 기준(위에서부터 비교):
    1) 최소 장부 부족확률  2) 계획 장부 부족확률   (낮을수록 좋음, 0.1%p 단위로 묶어 그 안의 차이는 동률)
    3) 계획 장부 하위 5% 실질자산 평균(CVaR)      4) 계획 장부 실질자산 중앙값   (높을수록 좋음)
- 각 값은 22개 전략의 평균. 전략별로 같은 규칙을 적용했을 때 1등이 된 횟수를 함께 표시.
- 주 평가는 A씨 100세(2069년), 같은 규칙으로 90세(2059년) 순위도 계산해 유지 여부를 확인.
재확인
- 상위 조합을 새 seed로 다시 돌려 같은 규칙으로 순위를 매기고, 1등과 나머지의 차이를 경로 짝 비교로 추정.
  부족확률 차이: 경로별(22전략 평균) 차이의 평균과 정규근사 신뢰구간.
  CVaR·중앙값 차이: 경로 붓스트랩 신뢰구간. 비교 횟수만큼 Bonferroni 보정.
"""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import NormalDist

import numpy as np

TIE_BIN = 0.001  # 0.1%p
METRICS = {
    100: ("minimum_shortfall_prob_100", "plan_shortfall_prob_100",
          "plan_terminal_real_cvar05", "plan_terminal_real_p50"),
    90: ("minimum_shortfall_prob_90", "plan_shortfall_prob_90",
         "plan_real_cvar05_90", "plan_real_p50_90"),
}
DECISION_KEYS = ("a_claim_age", "spouse_claim_age", "a_method", "spouse_method",
                 "a_payout_years", "spouse_payout_years")


def rank_key(min_p, plan_p, cvar, median):
    return (math.floor(min_p / TIE_BIN + 1e-9), math.floor(plan_p / TIE_BIN + 1e-9), -cvar, -median)


def _is_current_living(row):
    return row.get("living_change_year") is None


def _by_combo(rows):
    out = defaultdict(list)
    for r in rows:
        if r.get("valid", True):
            out[r["combo_id"]].append(r)
    return out


def rank_combos(rows, age=100):
    """현행 생활비 조합의 순위 목록(1등부터)."""
    names = METRICS[age]
    combos = {cid: rs for cid, rs in _by_combo(rows).items() if _is_current_living(rs[0])}
    summary = []
    for cid, rs in combos.items():
        avg = [float(np.mean([r[n] for r in rs])) for n in names]
        summary.append({"combo_id": cid, **{k: rs[0][k] for k in DECISION_KEYS},
                        "avg_minimum_shortfall_prob": avg[0], "avg_plan_shortfall_prob": avg[1],
                        "avg_plan_real_cvar05": avg[2], "avg_plan_real_p50": avg[3],
                        "_key": rank_key(*avg)})
    # 전략별 1등 횟수
    strategies = sorted({r["strategy"] for rs in combos.values() for r in rs})
    wins = defaultdict(int)
    for s in strategies:
        best = min(((rank_key(*[r[n] for n in names]), cid)
                    for cid, rs in combos.items() for r in rs if r["strategy"] == s))[1]
        wins[best] += 1
    summary.sort(key=lambda x: (x["_key"], x["combo_id"]))
    for i, x in enumerate(summary, 1):
        x["rank"] = i
        x["strategies_ranked_first"] = wins[x["combo_id"]]
        x["n_strategies"] = len(strategies)
        del x["_key"]
    return summary


def living_sensitivity(rows):
    """같은 (국민연금·퇴직급여) 조합에서 생활비 변경안이 현행 대비 얼마나 달라지는지 (22전략 평균)."""
    groups = defaultdict(dict)
    for cid, rs in _by_combo(rows).items():
        r0 = rs[0]
        dkey = tuple(r0[k] for k in DECISION_KEYS)
        lkey = "현행" if r0["living_change_year"] is None else \
            f"{r0['living_change_year']}년부터 월 {r0['monthly_living_after_change']:,}원"
        groups[dkey][lkey] = {n: float(np.mean([r[n] for r in rs])) for n in METRICS[100]}
    out = []
    for dkey, opts in groups.items():
        base = opts.get("현행")
        for lkey, vals in opts.items():
            row = dict(zip(DECISION_KEYS, dkey))
            row["living_option"] = lkey
            for n, v in vals.items():
                row[f"avg_{n}"] = v
                row[f"delta_{n}"] = None if base is None else v - base[n]
            out.append(row)
    return out


def _cvar(x, axis=0):
    k = max(1, int(0.05 * x.shape[axis]))
    return np.sort(x, axis=axis)[:k].mean(axis=axis)


def recheck_statistics(grid, paths, alpha=0.05, n_boot=1000, boot_seed=20261116):
    """재확인 실행 결과(경로별 배열)로 순위와 1등 대비 차이 신뢰구간을 계산.

    paths: run_decision_grid(..., return_paths=True)["paths"]
      short[path, combo, strategy, ledger(0=min,1=plan), age_index(0=90,1=95,2=100)]
      terminal_real_100[path, combo, strategy]
    """
    short = paths["short"]
    term = paths["terminal_real_100"]
    n, G, S = term.shape
    min_rate = short[:, :, :, 0, 2].mean(axis=2)   # 경로별 22전략 중 부족 비율 [path, combo]
    plan_rate = short[:, :, :, 1, 2].mean(axis=2)
    cvar = _cvar(term).mean(axis=1)                 # 전략별 CVaR의 22전략 평균 [combo]
    med = np.median(term, axis=0).mean(axis=1)
    keys = [rank_key(min_rate[:, g].mean(), plan_rate[:, g].mean(), cvar[g], med[g]) for g in range(G)]
    order = sorted(range(G), key=lambda g: (keys[g], grid[g]["combo_id"]))
    top = order[0]
    m = max(1, G - 1)
    z = NormalDist().inv_cdf(1 - alpha / m / 2)
    rng = np.random.default_rng(boot_seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    comps = []
    for g in order[1:]:
        res = {"combo_id": grid[g]["combo_id"], "vs": grid[top]["combo_id"]}
        for name, arr in (("minimum_shortfall", min_rate), ("plan_shortfall", plan_rate)):
            d = arr[:, g] - arr[:, top]
            se = d.std(ddof=1) / math.sqrt(n) if n > 1 else 0.0
            res[f"{name}_diff"] = float(d.mean())
            res[f"{name}_ci"] = [float(d.mean() - z * se), float(d.mean() + z * se)]
        bc, bm = [], []
        for b in range(n_boot):
            tb = term[idx[b]]
            bc.append(_cvar(tb[:, g]).mean() - _cvar(tb[:, top]).mean())
            bm.append(np.median(tb[:, g], axis=0).mean() - np.median(tb[:, top], axis=0).mean())
        lo, hi = 100 * alpha / m / 2, 100 * (1 - alpha / m / 2)
        res["cvar05_diff"] = float(cvar[g] - cvar[top])
        res["cvar05_ci"] = [float(np.percentile(bc, lo)), float(np.percentile(bc, hi))]
        res["median_diff"] = float(med[g] - med[top])
        res["median_ci"] = [float(np.percentile(bm, lo)), float(np.percentile(bm, hi))]
        # 1등보다 확실히 나쁜지: 부족확률 차이 CI 하한 > 0 또는 자산 차이 CI 상한 < 0
        res["clearly_worse_than_top"] = bool(
            res["minimum_shortfall_ci"][0] > 0 or res["plan_shortfall_ci"][0] > 0
            or res["cvar05_ci"][1] < 0 or res["median_ci"][1] < 0)
        comps.append(res)
    ranking = [{"rank": i + 1, "combo_id": grid[g]["combo_id"],
                **{k: grid[g][k] for k in DECISION_KEYS},
                "avg_minimum_shortfall_prob": float(min_rate[:, g].mean()),
                "avg_plan_shortfall_prob": float(plan_rate[:, g].mean()),
                "avg_plan_real_cvar05": float(cvar[g]), "avg_plan_real_p50": float(med[g])}
               for i, g in enumerate(order)]
    return {"ranking": ranking, "comparisons_vs_top": comps,
            "bonferroni_comparisons": m, "familywise_alpha": alpha, "bootstrap_draws": n_boot}
