"""AFPK integrated simulation: correlated annual market-return paths.

Input: data/market/market_assumptions_*.json created by market_data.py.
Order of assets is read from the JSON (cash, bond_kr, equity_kr); portfolio
weights must use that same order. No taxes or transaction fees are applied here.

Each entry of the output array is an *annual simple return* (not log return).
Market scenarios are sampled once per path and are reusable across all 22
strategies, to provide common random numbers for fair comparisons.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class MarketAssumptions:
    assets: tuple[str, ...]
    annual_log_means: np.ndarray
    annual_log_cov: np.ndarray
    as_of: str = ""


def load_market_assumptions(path: str | Path) -> MarketAssumptions:
    """Load and validate the team's annual joint-lognormal market assumptions."""
    with Path(path).open("r", encoding="utf-8") as file:
        doc = json.load(file)
    assets = tuple(doc["assets"])
    means = np.asarray(doc["annual_log_means"], dtype=float)
    cov = np.asarray(doc["annual_log_cov"], dtype=float)
    n = len(assets)
    if n == 0 or len(set(assets)) != n:
        raise ValueError("assets must be nonempty and unique")
    if means.shape != (n,) or cov.shape != (n, n):
        raise ValueError("annual_log_means/cov dimensions do not match assets")
    if not np.isfinite(means).all() or not np.isfinite(cov).all():
        raise ValueError("market assumptions must be finite")
    if not np.allclose(cov, cov.T, rtol=0.0, atol=1e-12):
        raise ValueError("annual_log_cov must be symmetric")
    # The supplied baseline is positive definite; fail clearly for unsupported
    # degenerate matrices rather than silently altering assumptions.
    try:
        np.linalg.cholesky(cov)
    except np.linalg.LinAlgError as exc:
        raise ValueError("annual_log_cov must be positive definite") from exc

    if "annual_expected_simple_returns" in doc:
        stated = np.asarray(doc["annual_expected_simple_returns"], dtype=float)
        derived = np.exp(means + 0.5 * np.diag(cov)) - 1.0
        if stated.shape != (n,) or not np.allclose(stated, derived, rtol=0.0, atol=5e-4):
            raise ValueError("simple-return assumptions conflict with log moments")

    return MarketAssumptions(assets, means, cov, str(doc.get("as_of", "")))


def generate_asset_returns(
    assumptions: MarketAssumptions,
    *,
    n_paths: int,
    years: Sequence[int],
    seed: int,
) -> np.ndarray:
    """Return shape (n_paths, n_years, n_assets) of annual simple returns."""
    years = tuple(int(year) for year in years)
    if n_paths <= 0 or not years:
        raise ValueError("n_paths and years must be nonempty and positive")
    if sorted(set(years)) != list(years):
        raise ValueError("years must be strictly increasing and unique")
    rng = np.random.default_rng(seed)
    log_returns = rng.multivariate_normal(
        mean=assumptions.annual_log_means,
        cov=assumptions.annual_log_cov,
        size=(n_paths, len(years)),
        method="cholesky",
    )
    return np.expm1(log_returns)


def portfolio_returns(asset_returns: np.ndarray, weights: Sequence[float]) -> np.ndarray:
    """Weighted *simple* returns for all paths and years; returns (paths, years)."""
    arr = np.asarray(asset_returns, dtype=float)
    w = np.asarray(weights, dtype=float)
    if arr.ndim != 3 or w.shape != (arr.shape[2],):
        raise ValueError("asset_returns must be [path, year, asset] with matching weights")
    if not np.isfinite(w).all() or np.any(w < -1e-12):
        raise ValueError("weights must be finite and nonnegative")
    if not np.isclose(w.sum(), 1.0, rtol=0.0, atol=1e-8):
        raise ValueError("portfolio weights must sum to one")
    return np.einsum("pya,a->py", arr, w)


def returns_by_year(years: Sequence[int], portfolio_yearly_returns: Sequence[float]) -> dict[int, float]:
    """Return a dict suitable for run_full_simulation(investment_returns=...)."""
    years = tuple(map(int, years))
    values = np.asarray(portfolio_yearly_returns, dtype=float)
    if values.shape != (len(years),):
        raise ValueError("Expected one portfolio return per year")
    if not np.isfinite(values).all():
        raise ValueError("Returns must be finite")
    return {year: float(value) for year, value in zip(years, values)}
