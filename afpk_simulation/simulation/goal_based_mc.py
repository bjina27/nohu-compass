"""AFPK goal-based household Monte Carlo, with two spending ledgers per path.

This runner DOES NOT recompute income, pension or family events. It invokes
existing full_simulation.run_full_simulation twice for each path/strategy:
  minimum: minimum living + debt + all health shocks + opted-in essential
           recurring family support; NO discretionary child one-time transfer.
  plan:    original spending and affordability-cap logic unchanged.
Same master_seed and the same market path are applied to both ledgers.

Decision order (fixed BEFORE running): minimum shortage, plan shortage,
optional child support goal miss, lowest expected portfolio volatility;
paired exact one-sided tests with Bonferroni over all strategy pairs/stages.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

import numpy as np

from simulation.market_paths import load_market_assumptions, generate_asset_returns
from simulation.portfolio_policy import target_weights
from simulation.risk_metrics import simple_return_covariance, expected_annual_volatility
from simulation.paired_selection import selection_stages
from simulation.simulation_metrics import path_outcome, aggregate_outcomes


def _child_goal_outcome(rows: list[dict], end_year: int) -> tuple[bool, bool]:
    """(miss, goal_was_due) among rows through the decision horizon."""
    subset = [r for r in rows if r['year'] <= end_year]
    due = any(float(r.get('son_target_one_time_support', 0)) > 0 for r in subset)
    miss = any(float(r.get('son_support_capacity_shortfall', 0)) > 0 for r in subset)
    if miss and not due:
        raise ValueError('Child goal missed with no positive goal target')
    return miss, due


def _risk_profile_status(contract: dict, risk_need_grade: str | None, risk_capacity_grade: str | None) -> dict:
    """Grades MUST be consultation-confirmed on a matching low/moderate/high scale.

    The contract's current risk_capacity CFA grade is unresolved. Do NOT map
    a numeric G&L questionnaire score into a hard stock-weight cutoff.
    """
    grades = {'low': 1, 'moderate': 2, 'high': 3}
    inputs = contract.get('risk_inputs_status', {})
    found_need = inputs.get('risk_need', {}).get('label')
    capacity_note = inputs.get('risk_capacity', {}).get('cfa_2026')
    result = {
        'contract_risk_need_label': found_need,
        'contract_risk_capacity_note': capacity_note,
        'risk_tolerance': inputs.get('risk_tolerance', {}),
        'manually_confirmed_risk_need': risk_need_grade,
        'manually_confirmed_risk_capacity': risk_capacity_grade,
    }
    if risk_need_grade is None or risk_capacity_grade is None:
        result['decision'] = 'review_required_unconfirmed_comparable_grades'
        result['recommendation_status'] = 'provisional_only'
    elif risk_need_grade not in grades or risk_capacity_grade not in grades:
        raise ValueError('risk grades must be low, moderate, high or absent')
    elif grades[risk_need_grade] > grades[risk_capacity_grade]:
        result['decision'] = 'need_exceeds_ability_adjust_goals'
        result['recommendation_status'] = 'on_hold'
    else:
        result['decision'] = 'no_need_capacity_conflict_under_confirmed_grades'
        result['recommendation_status'] = 'provisional_pending_suitability_review'
    return result


def run_goal_based_mc(
    *,
    contract: dict,
    market_json: str | Path,
    household_runner: Callable,
    n_paths: int,
    years: list[int] | range,
    base_seed: int = 20261114,
    birth_year: int = 1969,
    target_ages: tuple[int, ...] = (90, 95, 100),
    decision_age: int = 100,
    essential_family_support: tuple[str, ...] = (),
    include_child_goal: bool = False,
    familywise_alpha: float = 0.05,
    risk_need_grade: str | None = None,
    risk_capacity_grade: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    if n_paths < 1:
        raise ValueError('n_paths must be positive')
    years = list(years)
    if not years or years != list(range(years[0], years[-1] + 1)):
        raise ValueError('years must be consecutive and nonempty')
    if decision_age not in target_ages:
        raise ValueError('decision_age must be among target_ages')
    age_to_year = {age: birth_year + age for age in target_ages}
    if any(y not in years for y in age_to_year.values()):
        raise ValueError('age horizon outside simulation years')
    if 'allocation_rule' not in contract:
        raise ValueError('final rule requires updated step4_strategies.json with allocation_rule')
    if tuple(contract['asset_order']) != ('cash', 'bond_kr', 'equity_kr'):
        raise ValueError('required asset order: cash, bond_kr, equity_kr')
    essential_family_support = tuple(essential_family_support)
    from simulation.spending_policy import validate_spending_policy
    min_living = float(contract['emergency_fund_basis']['monthly_min_living_2026'])
    min_policy = validate_spending_policy({
        'mode': 'minimum', 'monthly_min_living_2026': min_living,
        'essential_family_support': essential_family_support,
    }, plan_monthly_living=1e100)  # The engine validates against its actual config.
    market = load_market_assumptions(market_json)
    if market.assets != tuple(contract['asset_order']):
        raise ValueError('market assets and strategies do not match')
    paths = generate_asset_returns(market, n_paths=n_paths, years=years, seed=base_seed)
    simple_cov = simple_return_covariance(market.annual_log_means, market.annual_log_cov)
    strategies = contract['strategies']
    if len(strategies) != 22 or len(set(s['id'] for s in strategies)) != 22:
        raise ValueError('exactly 22 distinct strategies required')
    basis = contract['emergency_fund_basis']
    year_index = {y: j for j, y in enumerate(years)}

    outcomes = defaultdict(list)
    failure_vectors = {
        metric: {s['id']: [] for s in strategies}
        for metric in (('minimum', 'plan', 'child_goal'))
    }
    conditional_goals = {s['id']: [0, 0] for s in strategies}  # due, miss
    vol_sum = {s['id']: 0.0 for s in strategies}
    vol_count = {s['id']: 0 for s in strategies}
    nesting_violation_count = 0
    for p in range(n_paths):
        household_seed = base_seed + 1_000_000 + p
        one_market_path = paths[p]
        for s in strategies:
            sid = s['id']
            modes = {}
            for mode in ('minimum', 'plan'):
                def dynamic_return(year, state, *, _s=s, _path=one_market_path, _mode=mode):
                    w = target_weights(
                        year=year,
                        financial_assets=float(state['opening_assets']),
                        emergency_months=int(_s['emergency_months']),
                        equity_share_of_remainder=float(_s['equity_share_of_remainder']),
                        basis=basis,
                    )
                    if _mode == 'plan' and state['opening_assets'] > 0:
                        vol_sum[_s['id']] += expected_annual_volatility(w, simple_cov)
                        vol_count[_s['id']] += 1
                    return float(np.dot(w, _path[year_index[year]]))

                rows = household_runner(
                    master_seed=household_seed,
                    investment_return_fn=dynamic_return,
                    spending_policy=min_policy if mode == 'minimum' else None,
                )
                if not isinstance(rows, list) or [int(r['year']) for r in rows] != years:
                    raise ValueError(f'incorrect annual rows for strategy {sid}, mode {mode}')
                modes[mode] = rows
            for age, end_year in age_to_year.items():
                minimum = path_outcome(modes['minimum'], end_year=end_year)
                plan = path_outcome(modes['plan'], end_year=end_year)
                outcomes[(sid, 'minimum', age)].append(minimum)
                outcomes[(sid, 'plan', age)].append(plan)
                if minimum['shortfall'] and not plan['shortfall']:
                    nesting_violation_count += 1
                goal_miss, goal_due = _child_goal_outcome(modes['plan'], end_year)
                outcomes[(sid, 'child_goal', age)].append({
                    'shortfall': goal_miss, 'goal_due': goal_due,
                })
                if age == decision_age:
                    failure_vectors['minimum'][sid].append(minimum['shortfall'])
                    failure_vectors['plan'][sid].append(plan['shortfall'])
                    failure_vectors['child_goal'][sid].append(goal_miss)
                    conditional_goals[sid][0] += int(goal_due)
                    conditional_goals[sid][1] += int(goal_miss)
        if on_progress:
            on_progress(p + 1, n_paths)

    summary = []
    for s in strategies:
        sid = s['id']
        for age in target_ages:
            minimum = aggregate_outcomes(outcomes[(sid, 'minimum', age)])
            plan = aggregate_outcomes(outcomes[(sid, 'plan', age)])
            goal_results = outcomes[(sid, 'child_goal', age)]
            misses = sum(bool(x['shortfall']) for x in goal_results)
            due = sum(bool(x['goal_due']) for x in goal_results)
            summary.append({
                'strategy': sid, 'emergency_months': s['emergency_months'],
                'equity_share_of_remainder': s['equity_share_of_remainder'],
                'target_age': age, 'end_year': age_to_year[age],
                'n_paths': n_paths,
                'minimum_shortfall_count': minimum['n_shortfall_paths'],
                'minimum_shortfall_probability': minimum['shortfall_probability'],
                'plan_shortfall_count': plan['n_shortfall_paths'],
                'plan_shortfall_probability': plan['shortfall_probability'],
                'child_goal_due_count': due,
                'child_goal_miss_count': misses,
                'child_goal_miss_probability_all_paths': misses / n_paths,
                'child_goal_miss_probability_given_goal': (misses / due) if due else None,
                'mean_cumulative_unfunded_plan': plan['mean_cumulative_unfunded_all_paths'],
                'median_terminal_assets_plan': plan['median_terminal_assets'],
                'mean_terminal_assets_plan': plan['mean_terminal_assets'],
                'mean_expected_annual_volatility_plan': (
                    vol_sum[sid] / vol_count[sid] if vol_count[sid] else None
                ),
            })

    stages = ['minimum', 'plan'] + (['child_goal'] if include_child_goal else [])
    selection = selection_stages(
        failure_vectors, stage_names=stages, familywise_alpha=familywise_alpha
    )
    by_id = {s['id']: s for s in strategies}
    # Prespecified decision: smallest mean conditional expected simple-return vol.
    def tie_break(sid):
        avg_vol = vol_sum[sid] / vol_count[sid] if vol_count[sid] else float('inf')
        return (avg_vol, float(by_id[sid]['equity_share_of_remainder']),
                -int(by_id[sid]['emergency_months']), sid)
    winner = min(selection['survivors'], key=tie_break)
    selection['chosen_strategy'] = winner
    selection['ranking_rule'] = (
        'lowest mean annual expected SIMPLE portfolio volatility of all years'
        ' with positive opening assets on PLAN ledger; ties: lower target equity'
        ' share, more emergency months, strategy ID'
    )
    profile = _risk_profile_status(contract, risk_need_grade, risk_capacity_grade)
    return {
        'market_json': str(market_json), 'n_paths': n_paths, 'base_seed': base_seed,
        'decision_age': decision_age, 'target_ages': list(target_ages),
        'essential_family_support': list(essential_family_support),
        'minimum_monthly_living_2026': min_living,
        'child_goal_in_selection': include_child_goal,
        'allocation_method': 'dynamic_cash_midyear_return',
        'household_seed_policy': 'base_seed + 1000000 + path_index',
        'strategy_results': summary,
        'selection': selection,
        'risk_profile_check': profile,
        'minimum_failure_not_in_plan_count': nesting_violation_count,
        'notes': [
            'A minimum ledger excludes all optional child one-time support.',
            'Family recurring support in the minimum ledger is consultation-selected.',
            'Both ledgers share the same reemployment/parent/child seeds and market path.',
            'Risk selection uses a prechosen decision age and reference scenario.',
            'Discordant-pair exact test is not an equivalence test.',
            'Bonferroni alpha reserves all 231 pairs and all selection stages.',
            'Annual expected volatility uses converted SIMPLE-return lognormal covariance.',
            'Annual midpoint cashflow interest is posted only at year end.',
            'Shortage only captures year-end deficit; intrayear liquidity not modeled.',
            'Market assumptions may be after tax, while product fees are not deducted.',
        ],
    }
