"""AFPK Monte Carlo STEP 2: same household/market shocks, all 22 portfolios.

This integrates with existing `full_simulation.run_full_simulation`, which
already computes child affordability, investment profits, and unmet funding.
No external portfolio accounting duplicates household engine calculations.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np

from simulation.market_paths import (
    generate_asset_returns, load_market_assumptions, portfolio_returns, returns_by_year,
)
from simulation.simulation_metrics import path_outcome, aggregate_outcomes
from simulation.portfolio_policy import target_weights


def load_contract(path: str | Path) -> dict:
    with Path(path).open('r', encoding='utf-8') as f:
        contract = json.load(f)
    strategies = contract['strategies']
    if len(strategies) != 22:
        raise ValueError(f'Expected 22 strategies, got {len(strategies)}')
    ids = [s['id'] for s in strategies]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate strategy ids')
    assets = tuple(contract['asset_order'])
    for s in strategies:
        w = np.asarray(s['weights'], dtype=float)
        if w.shape != (len(assets),) or not np.isfinite(w).all() or (w < 0).any():
            raise ValueError(f'Invalid weights: {s["id"]}')
        if not np.isclose(w.sum(), 1, atol=1e-8, rtol=0):
            raise ValueError(f'Weights do not total 1: {s["id"]}')
    return contract


def run_mc(
    *,
    contract: dict,
    market_json: str | Path,
    household_runner: Callable,
    n_paths: int,
    years: list[int] | range,
    base_seed: int = 20261114,
    birth_year: int = 1969,
    target_ages: tuple[int, ...] = (90, 95, 100),
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Runs a *pilot* Monte Carlo and aggregates path failures by target age.

    For each index, household master_seed is identical for every strategy.
    The same pre-generated market returns are reweighted for each strategy.
    This is a common-random-numbers comparison. An actual family cashflow
    may still depend on the strategy via affordability decisions.

    The module trusts existing engine investment mechanics and takes only
    `unfunded_amount`/`closing_assets` out of its yearly output.
    """
    if n_paths <= 0:
        raise ValueError('n_paths must be positive')
    years = list(years)
    if years != list(range(years[0], years[-1] + 1)):
        raise ValueError('years must be consecutive')
    age_to_year = {age: birth_year + age for age in target_ages}
    if any(y not in years for y in age_to_year.values()):
        raise ValueError('At least one age horizon is outside the simulation years')

    market = load_market_assumptions(market_json)
    if tuple(contract['asset_order']) != market.assets:
        raise ValueError('Market asset order disagrees with strategy contract')
    paths = generate_asset_returns(market, n_paths=n_paths, years=years, seed=base_seed)
    strategies = contract['strategies']
    # Old contracts without allocation_rule retain the old fixed-weight behavior.
    # New team contract activates BOTH dynamic weights AND midyear cashflows.
    dynamic = 'allocation_rule' in contract
    if dynamic:
        if any('equity_share_of_remainder' not in s for s in strategies):
            raise ValueError('Dynamic allocation requires equity_share_of_remainder for all strategies')
        basis = contract['emergency_fund_basis']
        if tuple(contract['asset_order']) != ('cash', 'bond_kr', 'equity_kr'):
            raise ValueError('Dynamic policy expects cash, bond_kr, equity_kr asset order')
    else:
        returns = {s['id']: portfolio_returns(paths, s['weights']) for s in strategies}
    year_index = {year: i for i, year in enumerate(years)}
    outcomes = {(s['id'], age): [] for s in strategies for age in target_ages}

    # Re-use identical household seeds and market path indexes for all strategies.
    for p in range(n_paths):
        household_seed = base_seed + 1000000 + p
        for s in strategies:
            if dynamic:
                asset_return_path = paths[p]  # same market path for all 22 strategies

                def dynamic_annual_return(year, state, *, _s=s, _market=asset_return_path):
                    w = target_weights(
                        year=year,
                        financial_assets=float(state['opening_assets']),
                        emergency_months=int(_s['emergency_months']),
                        equity_share_of_remainder=float(_s['equity_share_of_remainder']),
                        basis=basis,
                    )
                    return float(np.dot(w, _market[year_index[year]]))

                rows = household_runner(
                    master_seed=household_seed,
                    investment_return_fn=dynamic_annual_return,
                )
            else:
                annual_returns = returns_by_year(years, returns[s['id']][p])
                rows = household_runner(master_seed=household_seed, investment_returns=annual_returns)
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
                raise TypeError('run_full_simulation must return list[dict] (return_details=False)')
            seen_years = [int(row['year']) for row in rows]
            if seen_years != years:
                raise ValueError(f'Household result years mismatch for {s["id"]}: {seen_years[:3]}...')
            for age, end_year in age_to_year.items():
                outcomes[(s['id'], age)].append(path_outcome(rows, end_year=end_year))
        if on_progress:
            on_progress(p + 1, n_paths)

    summary = []
    for s in strategies:
        for age in target_ages:
            row = {
                'strategy': s['id'],
                'emergency_months': s['emergency_months'],
                'weights': s['weights'],
                'target_age': age,
                'end_year': age_to_year[age],
                **aggregate_outcomes(outcomes[(s['id'], age)]),
            }
            summary.append(row)
    return {
        'market_file': str(market_json),
        'n_paths': n_paths,
        'base_seed': base_seed,
        'household_seed_policy': 'master_seed = base_seed + 1000000 + path_index',
        'age_reference': f'A (birth_year={birth_year})',
        'years': [years[0], years[-1]],
        'allocation_method': 'dynamic_cash_midyear_return' if dynamic else 'fixed_weights_legacy',
        'strategy_results': summary,
        'notes': [
            'Monte Carlo standard errors capture sampling uncertainty only, not market-model uncertainty.',
            'Market assumptions are used as provided (pretax OR aftertax per selected JSON); no extra tax/fees are deducted.',
            'The household engine may make asset-dependent affordability decisions. Same seeds mean the same underlying RNG stream, not necessarily identical realized spending.',
            'New allocation_rule: annual reserve reweighting on opening assets, midpoint-flow return accrued and posted at year end; old contract: fixed weights and legacy returns.',
            'Dynamic reserve target applies only when allocation_rule exists in contract; cash reserve is never subtracted as an expense.',
        ],
    }
