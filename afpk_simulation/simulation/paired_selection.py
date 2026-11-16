"""Pre-registered paired rare-event comparisons with conservative FWER control.

The empirical best comparator is selected after sampling. To allow that
selection, the entire family of 22 choose 2 = 231 pairs is reserved at *each*
decision stage. The 5% familywise alpha is divided by pairs * stage_count.
This is conservative, but avoids a post-selection 21-comparisons claim.
"""
from __future__ import annotations

import math
from collections.abc import Mapping


def exact_one_sided_discordance_p(reference_failures, candidate_failures) -> tuple[float, int, int]:
    """Exact McNemar/binomial one-sided p for candidate having more failures.

    b = reference fails alone; c = candidate fails alone. H0 has p=0.5
    conditional on discordance. This tests equality, *not equivalence*.
    """
    reference = list(map(bool, reference_failures))
    candidate = list(map(bool, candidate_failures))
    if len(reference) != len(candidate) or not reference:
        raise ValueError('paired arrays must have the same positive length')
    b = sum(ref and not cand for ref, cand in zip(reference, candidate))
    c = sum(cand and not ref for ref, cand in zip(reference, candidate))
    n = b + c
    if n == 0:
        return 1.0, b, c
    # Exact, numerically stable binomial(1/2) tail. The shorter tail is summed.
    def mass(k: int) -> float:
        return math.exp(
            math.lgamma(n + 1) - math.lgamma(k + 1)
            - math.lgamma(n - k + 1) - n * math.log(2)
        )
    if c <= n // 2:
        p = 1.0 - math.fsum(mass(k) for k in range(c))
    else:
        p = math.fsum(mass(k) for k in range(c, n + 1))
    return max(0.0, min(1.0, p)), b, c


def selection_stages(
    failures_by_stage: Mapping[str, Mapping[str, list[bool]]],
    *,
    stage_names: list[str],
    familywise_alpha: float = 0.05,
) -> dict:
    """Eliminate statistically worse strategies per preordered stage.

    Alpha covers *all* unordered pairs among the initial candidates, times the
    number of prespecified stages. The benchmark may be selected from the data.
    No false equivalence inference is made when a candidate survives.
    """
    if not 0 < familywise_alpha < 1 or not stage_names:
        raise ValueError('invalid alpha or stages')
    ids = sorted(failures_by_stage[stage_names[0]])
    if len(ids) < 2:
        raise ValueError('at least two strategies are required')
    n = len(failures_by_stage[stage_names[0]][ids[0]])
    if n == 0:
        raise ValueError('at least one path is required')
    for stage in stage_names:
        if set(failures_by_stage[stage]) != set(ids):
            raise ValueError('strategy IDs differ across stages')
        if any(len(failures_by_stage[stage][sid]) != n for sid in ids):
            raise ValueError('outcome counts differ across strategies')

    all_pairs = len(ids) * (len(ids) - 1) // 2
    alpha_per_test = familywise_alpha / (all_pairs * len(stage_names))
    survivors = list(ids)
    logs = []
    for stage in stage_names:
        data = failures_by_stage[stage]
        benchmark = min(survivors, key=lambda sid: (sum(data[sid]), sid))
        remaining = []
        comparisons = []
        for sid in survivors:
            if sid == benchmark:
                remaining.append(sid)
                continue
            p, b, c = exact_one_sided_discordance_p(data[benchmark], data[sid])
            excluded = c > b and p < alpha_per_test
            comparisons.append({
                'strategy': sid, 'reference_only_failures_b': b,
                'candidate_only_failures_c': c, 'p_value_one_sided': p,
                'excluded_as_worse': excluded,
            })
            if not excluded:
                remaining.append(sid)
        logs.append({
            'stage': stage, 'benchmark': benchmark,
            'benchmark_failures': sum(data[benchmark]),
            'survivors': sorted(remaining),
            'removed': sorted(set(survivors) - set(remaining)),
            'comparisons': comparisons,
        })
        survivors = sorted(remaining)
    return {
        'initial_strategies': ids,
        'survivors': survivors,
        'alpha_familywise_across_all_stages': familywise_alpha,
        'num_reserved_pairs_per_stage': all_pairs,
        'num_stages': len(stage_names),
        'alpha_per_pair_one_sided': alpha_per_test,
        'logs': logs,
        'meaning': 'Surviving means not proven worse, NOT proven equivalent.',
    }
