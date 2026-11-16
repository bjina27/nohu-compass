"""Annual emergency-reserve target weights from step4_strategies.json.

This mirrors the team's published allocation_rule. It is deliberately
self-contained so the Monte Carlo can use it even if the team's
investment.asset_allocation.target_weights API differs across versions.

Order: cash, bond_kr, equity_kr (the JSON's asset_order).
"""
from __future__ import annotations

import math


def target_weights(
    year: int,
    financial_assets: float,
    emergency_months: int,
    equity_share_of_remainder: float,
    *,
    basis: dict,
) -> tuple[float, float, float]:
    """Return cash/bond/equity weights summing to 1 for each calendar year.

    If opening assets cannot cover the reserve target, hold 100% cash.
    The cash reserve is part of assets, NOT an expense or an extra deduction.
    """
    start_year = 2026
    if year < start_year:
        raise ValueError("Year cannot predate 2026")
    if not math.isfinite(financial_assets) or financial_assets < 0:
        raise ValueError("financial_assets must be finite and nonnegative")
    if emergency_months not in (3, 6):
        raise ValueError("emergency_months must be 3 or 6")
    if not 0 <= equity_share_of_remainder <= 1:
        raise ValueError("equity_share_of_remainder must be between 0 and 1")

    monthly_min_living = float(basis["monthly_min_living_2026"])
    monthly_mortgage = float(basis["monthly_mortgage"])
    mortgage_end_year = int(basis["mortgage_end_year"])
    annual_inflation = float(basis["inflation_rate"])
    if min(monthly_min_living, monthly_mortgage) < 0 or not -1 < annual_inflation <= 1:
        raise ValueError("Invalid essential spending assumptions")

    essential = monthly_min_living * (1 + annual_inflation) ** (year - start_year)
    if year <= mortgage_end_year:
        essential += monthly_mortgage
    target_cash = essential * emergency_months
    cash_share = min(1.0, target_cash / financial_assets) if financial_assets > 0 else 1.0
    remaining_share = 1 - cash_share
    equity_share = remaining_share * equity_share_of_remainder
    bond_share = remaining_share - equity_share
    return cash_share, bond_share, equity_share
