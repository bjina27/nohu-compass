"""AFPK household-path shortfall metrics, using engine's own funding semantics."""
from __future__ import annotations

from math import sqrt
from statistics import mean, median


def path_outcome(rows: list[dict], *, end_year: int) -> dict:
    """Shortfall = any positive `unfunded_amount` up to the specified year.

    The source engine floors closing_assets at zero and exposes unmet funding
    separately. Do not infer success from terminal assets alone.
    """
    selected = [r for r in rows if int(r['year']) <= end_year]
    if not selected or int(selected[-1]['year']) != end_year:
        raise ValueError(f'Missing annual household record for end_year={end_year}')
    deficits = [(int(r['year']), float(r['unfunded_amount'])) for r in selected]
    if any(amount < -1e-9 for _, amount in deficits):
        raise ValueError('unfunded_amount must be nonnegative')
    positive = [(year, amount) for year, amount in deficits if amount > 1e-7]
    return {
        'shortfall': bool(positive),
        'first_shortfall_year': positive[0][0] if positive else None,
        'cumulative_unfunded': sum(amount for _, amount in positive),
        'terminal_assets': float(selected[-1]['closing_assets']),
    }


def _wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    # Approximate 95% CI for MC-estimated binary path outcomes, not for model uncertainty.
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    span = z * sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denominator
    return max(0, center - span), min(1, center + span)


def aggregate_outcomes(outcomes: list[dict]) -> dict:
    if not outcomes:
        raise ValueError('Cannot aggregate zero paths')
    n = len(outcomes)
    k = sum(bool(o['shortfall']) for o in outcomes)
    shortfall_amounts = [float(o['cumulative_unfunded']) for o in outcomes]
    terminal = sorted(float(o['terminal_assets']) for o in outcomes)
    lower, upper = _wilson_interval(k, n)
    return {
        'n_paths': n,
        'n_shortfall_paths': k,
        'shortfall_probability': k / n,
        'shortfall_probability_ci95_mc_only': [lower, upper],
        'mean_cumulative_unfunded_all_paths': mean(shortfall_amounts),
        'mean_cumulative_unfunded_if_shortfall': (
            mean(o['cumulative_unfunded'] for o in outcomes if o['shortfall']) if k else 0.0
        ),
        'mean_terminal_assets': mean(terminal),
        'median_terminal_assets': median(terminal),
        'min_terminal_assets': terminal[0],
        'max_terminal_assets': terminal[-1],
    }
