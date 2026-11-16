"""Explicit plan vs minimum spending policies for the AFPK household engine.

The minimum ledger retains the same stochastic events, pension, debt and health
costs as the plan ledger, but never pays discretionary one-time child support.
Recurring family support is included only when designated essential by the user.
No automatic discretionary spending increase is allowed in the minimum ledger.
"""
from __future__ import annotations

import math

FAMILY_KEYS = frozenset({'son', 'a_mother', 'spouse_mother'})


def validate_spending_policy(policy: dict | None, *, plan_monthly_living: float) -> dict:
    """Return a normalized policy, preserving legacy plan behavior for None."""
    if policy is None:
        return {'mode': 'plan', 'essential_family_support': ()}
    if not isinstance(policy, dict):
        raise TypeError('spending_policy must be a dict or None')
    mode = policy.get('mode', 'plan')
    if mode not in ('plan', 'minimum'):
        raise ValueError('spending_policy.mode must be plan or minimum')
    family = policy.get('essential_family_support', ())
    if not isinstance(family, (tuple, list, set)) or any(x not in FAMILY_KEYS for x in family):
        raise ValueError('essential_family_support supports son, a_mother, spouse_mother')
    if mode == 'minimum':
        living = policy.get('monthly_min_living_2026')
        if isinstance(living, bool) or not isinstance(living, (float, int)) or not math.isfinite(living):
            raise ValueError('minimum ledger requires monthly_min_living_2026')
        if living < 0 or living > plan_monthly_living:
            raise ValueError('minimum living must be between zero and plan living')
    return {
        'mode': mode,
        'monthly_min_living_2026': float(policy['monthly_min_living_2026']) if mode == 'minimum' else None,
        'essential_family_support': tuple(sorted(set(family))),
    }


def apply_spending_policy(
    expenses: dict,
    *,
    year: int,
    start_year: int,
    inflation_rate: float,
    policy: dict,
) -> dict:
    """Adjust ordinary living and regular family costs, not debt/health shocks."""
    if policy['mode'] == 'plan':
        return expenses
    data = dict(expenses)
    data['living'] = round(
        policy['monthly_min_living_2026'] * 12
        * (1 + inflation_rate) ** (year - start_year)
    )
    essential = set(policy['essential_family_support'])
    for name in FAMILY_KEYS:
        if name not in essential:
            data[name] = 0
    data['family_support'] = sum(data[name] for name in FAMILY_KEYS)
    data['total'] = data['living'] + data['family_support']
    return data


def discretionary_child_one_time_allowed(policy: dict) -> bool:
    """One-time independence/marriage support is an optional goal, not a floor."""
    return policy['mode'] == 'plan'
