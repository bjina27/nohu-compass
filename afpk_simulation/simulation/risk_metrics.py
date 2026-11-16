"""Expected simple-return volatility for dynamically rebalanced portfolios.

annual_log_cov belongs to *log* returns; the portfolio is a weighted sum of
*simple* returns exp(X)-1. Convert lognormal covariance exactly first.
"""
from __future__ import annotations
import numpy as np


def simple_return_covariance(annual_log_means, annual_log_cov) -> np.ndarray:
    mu = np.asarray(annual_log_means, dtype=float)
    cov = np.asarray(annual_log_cov, dtype=float)
    if cov.shape != (mu.size, mu.size):
        raise ValueError('market log-covariance shape does not match mean')
    gross_means = np.exp(mu + 0.5 * np.diag(cov))
    result = np.outer(gross_means, gross_means) * np.expm1(cov)
    return (result + result.T) / 2


def expected_annual_volatility(weights, simple_covariance) -> float:
    w = np.asarray(weights, dtype=float)
    cov = np.asarray(simple_covariance, dtype=float)
    var = float(w @ cov @ w)
    if var < -1e-12:
        raise ValueError('negative portfolio variance')
    return float(np.sqrt(max(0.0, var)))
