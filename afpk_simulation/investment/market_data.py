# -*- coding: utf-8 -*-
"""AFPK 시장 가정 모듈: 팀원 개발용 실행 가능한 기본 골격.

책임: 검증된 월별 *단순 총수익률*로 연간 로그수익률 공분산/상관을 추정하고,
      출처가 명시된 별도 기대수익률 가정으로 Monte Carlo 입력을 만든다.
비책임: 데이터 수집 API, 자산배분, 수익률 경로 생성, 투자 추천.
실제 시장 수익률 관측치는 이 파일에 내장하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import json
import math

import numpy as np
import pandas as pd

ASSETS = ("cash", "bond_kr", "equity_kr")  # 순서 불변! 팀 공통 인터페이스
REQUIRED_SERIES_TYPES = {
    "cash": "rate_proxy",
    "bond_kr": "total_return",
    "equity_kr": "total_return",
}


@dataclass(frozen=True)
class MarketAssumptions:
    as_of: str
    assets: tuple[str, ...]
    annual_expected_simple_returns: np.ndarray  # E[R], 소수(0.04=4%)
    annual_log_means: np.ndarray                # m = ln(1+mu)-diag(Sigma)/2
    annual_log_cov: np.ndarray                  # 연간 로그수익률 공분산
    annual_log_vol: np.ndarray                  # sqrt(diag(Sigma))
    log_correlation: np.ndarray                 # 현금 분산 0이면 해당 상관 0(대각 1)
    history_start: str
    history_end: str
    n_months: int
    data_provenance: dict
    return_assumption_provenance: dict

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of, "assets": list(self.assets),
            "annual_expected_simple_returns": self.annual_expected_simple_returns.tolist(),
            "annual_log_means": self.annual_log_means.tolist(),
            "annual_log_cov": self.annual_log_cov.tolist(),
            "annual_log_vol": self.annual_log_vol.tolist(),
            "log_correlation": self.log_correlation.tolist(),
            "history_start": self.history_start, "history_end": self.history_end,
            "n_months": self.n_months, "data_provenance": self.data_provenance,
            "return_assumption_provenance": self.return_assumption_provenance,
            "return_basis": "KRW nominal, before product fees and taxes",
            "simulation_rule": "annual asset simple return = exp(multivariate normal log return) - 1",
            "monte_carlo_handoff": MONTE_CARLO_HANDOFF,
        }


MONTE_CARLO_HANDOFF = {
    "asset_order": list(ASSETS),
    "step1_log_returns": "x[path, year, :] ~ MultivariateNormal(annual_log_means, annual_log_cov), 연도 간 독립(IID)",
    "step2_asset_simple_returns": "R = exp(x) - 1  (자산별 연 단순수익률)",
    "step3_fees": "자산별 연 보수 f_i를 R_i에서 차감: R_net_i = R_i - f_i (market_data에는 보수 미반영, monte_carlo.py에서 처리)",
    "step4_portfolio_return": "포트폴리오 연 단순수익률 r_p = sum_i w_i * R_net_i  — 자산별 '단순수익률'의 가중합. 로그수익률의 가중합이 아님 (market_data.portfolio_simple_return)",
    "step5_taxes": "세금(이자·배당소득세, 연금계좌 과세이연 등)은 계좌 유형별로 portfolio_engine.py에서 처리. market_data와 monte_carlo의 수익률은 세전",
    "rebalancing": "w는 매년 초 목표비중으로 리밸런싱한다고 가정할 때 위 식이 성립 (리밸런싱 규칙은 portfolio_engine 담당)",
    "numerical_note": "현금 분산이 매우 작아 공분산이 거의 특이행렬에 가까움. numpy multivariate_normal은 method='cholesky' 사용 권장",
    "units": "모든 값은 소수 (0.0332 = 3.32%), 원화·명목·연간",
}


def _month_end_dates(dates) -> pd.DatetimeIndex:
    parsed = pd.to_datetime(dates, errors="raise")
    if pd.isna(parsed).any():
        raise ValueError("날짜에 결측값이 있습니다.")
    return pd.DatetimeIndex(parsed).to_period("M").to_timestamp("M")


def _validate_monthly(df: pd.DataFrame, *, min_months: int = 36) -> pd.DataFrame:
    if tuple(df.columns) != ASSETS:
        raise ValueError(f"열 순서는 {ASSETS}이어야 합니다. 현재 {tuple(df.columns)}")
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("월별 데이터 인덱스는 DatetimeIndex여야 합니다.")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("월별 날짜는 중복 없이 오름차순이어야 합니다.")
    if len(df) < min_months:
        raise ValueError(f"공분산 추정에 필요한 관측월이 부족합니다: {len(df)} < {min_months}")
    periods = df.index.to_period("M")
    expected = pd.period_range(periods[0], periods[-1], freq="M")
    if not periods.equals(expected):
        missing = expected.difference(periods)
        raise ValueError(f"중간에 빠진 월이 있습니다. 임의 보간 금지: {list(map(str, missing[:6]))}")
    try:
        x = df.astype(float)
    except (TypeError, ValueError) as e:
        raise ValueError("수익률은 0.05처럼 소수 숫자여야 합니다(5가 아님).") from e
    if not np.isfinite(x.to_numpy()).all():
        raise ValueError("결측/무한대 수익률이 있습니다. 임의 채움 금지")
    if (x.to_numpy() <= -1).any():
        raise ValueError("단순수익률은 -100%보다 커야 로그변환할 수 있습니다.")
    if (x.abs().to_numpy() > 1).any():
        raise ValueError("월별 수익률 절댓값 100% 초과: 백분율(5)과 소수(0.05) 혼동 확인")
    return x


def read_monthly_returns_csv(path: str | Path) -> pd.DataFrame:
    """CSV 형식: month,cash,bond_kr,equity_kr (월말 날짜, 소수 수익률)."""
    df = pd.read_csv(path)
    required = {"month", *ASSETS}
    if set(df.columns) != required:
        raise ValueError(f"CSV 열은 month + {ASSETS}만 필요합니다.")
    dates = _month_end_dates(df["month"])
    out = df.loc[:, ASSETS].copy()
    out.index = dates
    return _validate_monthly(out)


def levels_to_monthly_simple_returns(levels: pd.DataFrame, *, value_column: str = "level") -> pd.Series:
    """date, level의 일별/월별 총수익지수를 월말 마지막 관측치로 추출해 pct_change.

    첫 월의 수익률은 그 이전 월말 관측치가 없으므로 버린다.
    이 함수는 '총수익' 지수인지 판별하지 못한다. 원자료 출처 확인은 필수.
    """
    if set(("date", value_column)) - set(levels.columns):
        raise ValueError(f"date, {value_column} 열이 필요합니다.")
    s = pd.Series(pd.to_numeric(levels[value_column], errors="raise").to_numpy(),
                  index=pd.to_datetime(levels["date"], errors="raise"), dtype=float)
    if s.index.has_duplicates or not s.index.is_monotonic_increasing:
        raise ValueError("지수 날짜는 중복 없이 오름차순이어야 합니다.")
    if not np.isfinite(s.to_numpy()).all() or (s <= 0).any():
        raise ValueError("지수 레벨은 양의 유한수여야 합니다.")
    monthly = s.groupby(s.index.to_period("M")).last()
    periods = pd.period_range(monthly.index[0], monthly.index[-1], freq="M")
    if not monthly.index.equals(periods):
        raise ValueError("지수에 빠진 월이 있습니다.")
    monthly.index = monthly.index.to_timestamp("M")
    return monthly.pct_change().iloc[1:]


def annual_yield_percent_to_monthly_simple(yield_pct: pd.Series) -> pd.Series:
    """월별 공시 연율 금리(예: 3.5=연 3.5%)를 월 복리 수익률 proxy로 환산.

    계약 금리/이자 발생 방식과 같다는 보장은 없으며 '현금 수익률 근사'이다.
    """
    y = yield_pct.astype(float).to_numpy() / 100.0
    if not np.isfinite(y).all() or (y <= -1).any():
        raise ValueError("연율 금리가 유효하지 않습니다.")
    return pd.Series(np.power(1 + y, 1 / 12) - 1, index=yield_pct.index, name="cash")


def estimate_market_assumptions(
    monthly_simple_returns: pd.DataFrame,
    annual_expected_simple_returns: Mapping[str, float],
    *, as_of: str,
    data_provenance: Mapping[str, Mapping[str, str]],
    return_assumption_provenance: Mapping[str, str],
    min_months: int = 36,
) -> MarketAssumptions:
    """기대수익률은 과거 수익률 평균으로 몰래 대체하지 않고 명시적으로 입력받는다.

    연간 공분산 Sigma = 12 * sample_cov(monthly log(1+R)), 독립 동일분포 근사.
    주어진 연간 단순 기대수익률 mu에 맞춘 로그정규 입력 m=ln(1+mu)-diag(Sigma)/2.
    실제 수익률의 꼬리/국면의존성은 이 모형에 반영되지 않는다.
    """
    df = _validate_monthly(monthly_simple_returns, min_months=min_months)
    cutoff = pd.Timestamp(as_of).to_period("M")
    if df.index[-1].to_period("M") > cutoff:
        raise ValueError("as_of 이후의 데이터를 포함할 수 없습니다 (look-ahead bias)")
    if set(annual_expected_simple_returns) != set(ASSETS):
        raise ValueError(f"기대수익률 자산 키는 정확히 {ASSETS}여야 합니다.")
    if set(data_provenance) != set(ASSETS) or set(return_assumption_provenance) != set(ASSETS):
        raise ValueError("세 자산 모두 원자료 및 기대수익률 출처가 필요합니다.")
    for asset in ASSETS:
        meta = data_provenance[asset]
        if meta.get("series_type") != REQUIRED_SERIES_TYPES[asset] or not meta.get("source_url") or not meta.get("series_name"):
            raise ValueError(f"{asset}: 올바른 총수익지수/금리 proxy 유형 및 출처가 필요합니다.")
        if not str(return_assumption_provenance[asset]).strip():
            raise ValueError(f"{asset}: 기대수익률의 산정 근거가 비어 있습니다.")
    mu = np.array([float(annual_expected_simple_returns[a]) for a in ASSETS])
    if not np.isfinite(mu).all() or (mu <= -1).any():
        raise ValueError("연간 단순 기대수익률은 -100% 초과 유한수여야 합니다.")
    logs = np.log1p(df.to_numpy(dtype=float))
    cov = np.atleast_2d(np.cov(logs, rowvar=False, ddof=1)) * 12.0
    cov = (cov + cov.T) / 2
    if np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError("공분산 행렬이 양의 준정부호가 아닙니다.")
    log_m = np.log1p(mu) - 0.5 * np.diag(cov)
    vol = np.sqrt(np.maximum(0, np.diag(cov)))
    denom = np.outer(vol, vol)
    corr = np.divide(cov, denom, out=np.zeros_like(cov), where=denom > 1e-15)
    np.fill_diagonal(corr, 1.0)  # 현금이 완전 상수면 상관은 수학적으로 정의되지 않음: 0으로 저장
    return MarketAssumptions(
        as_of=as_of, assets=ASSETS, annual_expected_simple_returns=mu,
        annual_log_means=log_m, annual_log_cov=cov, annual_log_vol=vol,
        log_correlation=corr, history_start=str(df.index[0].date()),
        history_end=str(df.index[-1].date()), n_months=len(df),
        data_provenance={k: dict(v) for k, v in data_provenance.items()},
        return_assumption_provenance=dict(return_assumption_provenance),
    )


def save_market_assumptions(result: MarketAssumptions, output_path: str | Path) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# 이하: 실데이터 수집 결과(raw CSV) → 월별 수익률 → 가정 JSON 파이프라인 (팀원 추가)
# 외부 네트워크 호출은 하지 않는다. raw 파일은 data/market/raw/에 사람이 내려받아 저장한다.
# ---------------------------------------------------------------------------

MODULE_ROOT = Path(__file__).resolve().parent.parent
MARKET_DIR = MODULE_ROOT / "data" / "market"
RAW_DIR = MARKET_DIR / "raw"


def read_ecos_monthly_rate_csv(path: str | Path) -> pd.Series:
    """ECOS 월별 금리 raw CSV(time=YYYYMM, value_annual_pct=연 %)를 월말 인덱스 Series로 읽는다.

    값의 단위는 '연 %'(3.25 = 연 3.25%)여야 한다. 빠진 월이 있으면 오류.
    """
    df = pd.read_csv(path, dtype={"time": str})
    if set(("time", "value_annual_pct")) - set(df.columns):
        raise ValueError("ECOS raw CSV에는 time, value_annual_pct 열이 필요합니다.")
    idx = pd.PeriodIndex(pd.to_datetime(df["time"], format="%Y%m"), freq="M")
    if idx.has_duplicates or not idx.is_monotonic_increasing:
        raise ValueError("ECOS 월 날짜는 중복 없이 오름차순이어야 합니다.")
    if not idx.equals(pd.period_range(idx[0], idx[-1], freq="M")):
        raise ValueError("ECOS 금리에 빠진 월이 있습니다. 임의 보간 금지")
    vals = pd.to_numeric(df["value_annual_pct"], errors="raise").astype(float)
    if (vals.abs() > 40).any() or (vals.abs().max() < 0.2 and len(vals) > 12):
        raise ValueError("금리 단위가 연 %인지 확인하세요(3.25 = 3.25%).")
    return pd.Series(vals.to_numpy(), index=idx.to_timestamp("M"), name="rate_pct")


def read_index_levels_csv(path: str | Path, *, date_column: str = "date",
                          value_column: str = "level") -> pd.DataFrame:
    """KRX 등에서 받은 일별 지수 raw CSV(date=YYYY-MM-DD 또는 YYYYMMDD, level)를 읽어
    levels_to_monthly_simple_returns()에 바로 넣을 수 있는 date, level DataFrame으로 반환."""
    df = pd.read_csv(path, dtype={date_column: str})
    if set((date_column, value_column)) - set(df.columns):
        raise ValueError(f"{date_column}, {value_column} 열이 필요합니다.")
    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_column].str.replace("/", "-"), errors="raise"),
        "level": pd.to_numeric(df[value_column].astype(str).str.replace(",", ""), errors="raise"),
    }).sort_values("date").reset_index(drop=True)
    return out


def build_monthly_returns(cash: pd.Series, bond_kr: pd.Series, equity_kr: pd.Series) -> pd.DataFrame:
    """세 자산의 월별 단순수익률을 '동시에 관측된 연속 구간'으로만 결합한다.

    - 교집합(inner join)만 사용. 겹치는 구간 안에 빈 월이 있으면 오류(보간 금지).
    - 열 순서는 ASSETS로 고정.
    """
    frame = pd.concat({"cash": cash, "bond_kr": bond_kr, "equity_kr": equity_kr}, axis=1, join="inner")
    frame = frame.loc[:, ASSETS].sort_index()
    if frame.empty:
        raise ValueError("세 시계열이 겹치는 월이 없습니다.")
    frame.index = pd.DatetimeIndex(frame.index).to_period("M").to_timestamp("M")
    frame.index.name = "month"
    return _validate_monthly(frame, min_months=1)


RAW_FILES = {
    "cash": "ecos_721Y001_2010000_CD91_monthly.csv",
    "bond_kr": "krx_ktb_prime_index_indTp5_monthend.csv",
    "equity_kr": "krx_kospi200_tr_1-175_monthend.csv",
}


def build_monthly_returns_from_raw(raw_dir: str | Path = RAW_DIR, *, as_of: str = "2026-10-31") -> pd.DataFrame:
    """data/market/raw/의 공식 원자료 3종 → 공통 구간 월별 단순수익률.

    cash   : ECOS CD(91일) 월평균 연 % → (1+y)^(1/12)-1 (같은 달 평균금리를 그 달의 수익률로 사용하는 근사)
    bond_kr: KRX 국고채프라임지수 총수익지수 월말(마지막 거래일) 수준 → pct_change
    equity : KRX 코스피 200 TR 월말(마지막 거래일) 수준 → pct_change
    as_of 이후 월은 버린다(look-ahead 방지).
    """
    raw_dir = Path(raw_dir)
    cutoff = pd.Timestamp(as_of).to_period("M")
    cash = annual_yield_percent_to_monthly_simple(read_ecos_monthly_rate_csv(raw_dir / RAW_FILES["cash"]))
    series = {"cash": cash}
    for asset in ("bond_kr", "equity_kr"):
        lv = read_index_levels_csv(raw_dir / RAW_FILES[asset])
        lv = lv[lv["date"].dt.to_period("M") <= cutoff]
        series[asset] = levels_to_monthly_simple_returns(lv)
    series["cash"] = series["cash"][series["cash"].index.to_period("M") <= cutoff]
    return build_monthly_returns(series["cash"], series["bond_kr"], series["equity_kr"])


def write_monthly_returns_csv(df: pd.DataFrame, path: str | Path) -> None:
    """month,cash,bond_kr,equity_kr 형식(월말 날짜, 소수 단순수익률)으로 저장."""
    x = _validate_monthly(df, min_months=1)
    out = x.copy()
    out.insert(0, "month", out.index.strftime("%Y-%m-%d"))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False, float_format="%.10f")


def assumption_consistency_error(result: MarketAssumptions) -> float:
    """max_i |exp(m_i + Sigma_ii/2) - 1 - mu_i| : 로그정규 정합성 오차."""
    rec = np.exp(result.annual_log_means + 0.5 * np.diag(result.annual_log_cov)) - 1
    return float(np.max(np.abs(rec - result.annual_expected_simple_returns)))


def portfolio_simple_return(asset_simple_returns: np.ndarray, weights) -> np.ndarray:
    """포트폴리오 단순수익률 = 자산별 단순수익률의 가중합 (로그수익률 가중합이 아님).

    asset_simple_returns: (..., 3) 배열, weights: 길이 3, 합 1.
    """
    w = np.asarray(weights, dtype=float)
    if w.shape != (len(ASSETS),) or not np.isclose(w.sum(), 1.0):
        raise ValueError("가중치는 길이 3, 합 1이어야 합니다.")
    return np.asarray(asset_simple_returns, dtype=float) @ w


def load_assumption_inputs(path: str | Path) -> dict:
    """assumptions_inputs.json을 읽는다. 기대수익률에 null이 남아 있으면 오류(미확정 값 사용 금지)."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    mu = d.get("annual_expected_simple_returns", {})
    missing = [a for a in ASSETS if mu.get(a) is None]
    if missing:
        raise ValueError(f"기대수익률 미확정(null): {missing}. 출처 확정 전에는 가정 JSON을 만들지 않습니다.")
    if tuple(d.get("asset_order", ASSETS)) != ASSETS:
        raise ValueError("asset_order가 팀 공통 순서와 다릅니다.")
    return d


def summarize(result: MarketAssumptions) -> str:
    lines = [f"as_of={result.as_of}  표본={result.history_start}~{result.history_end} ({result.n_months}개월)"]
    for i, a in enumerate(ASSETS):
        lines.append(f"  {a:9s} mu={result.annual_expected_simple_returns[i]:.4%}  "
                     f"m={result.annual_log_means[i]:.4%}  vol={result.annual_log_vol[i]:.4%}")
    lines.append("  log corr:\n" + np.array2string(result.log_correlation, precision=3))
    lines.append(f"  consistency error={assumption_consistency_error(result):.2e}  "
                 f"min eig={np.linalg.eigvalsh(result.annual_log_cov).min():.3e}")
    return "\n".join(lines)


def run_pipeline(inputs_path: str | Path = MARKET_DIR / "assumptions_inputs.json",
                 returns_csv: str | Path = MARKET_DIR / "monthly_returns.csv",
                 output_dir: str | Path = MARKET_DIR, *,
                 history_end: str | None = None, suffix: str = "",
                 mu_override: dict | None = None, override_note: str = "") -> MarketAssumptions:
    """monthly_returns.csv + assumptions_inputs.json → market_assumptions_YYYYMMDD{suffix}.json.

    history_end를 주면 위험모수(공분산) 추정 표본만 그 월까지로 자른다(민감도 세트용).
    기대수익률(mu)은 as_of 기준 그대로 유지한다.
    """
    inputs = load_assumption_inputs(inputs_path)
    returns = read_monthly_returns_csv(returns_csv)
    if history_end is not None:
        returns = returns[returns.index.to_period("M") <= pd.Timestamp(history_end).to_period("M")]
    mu = dict(inputs["annual_expected_simple_returns"])
    sources = dict(inputs["expected_return_sources"])
    if mu_override:
        for a, v in mu_override.items():
            if a not in ASSETS:
                raise ValueError(f"알 수 없는 자산: {a}")
            mu[a] = v
            sources[a] = f"[민감도 시나리오] {v:.4f}. {override_note}"
    result = estimate_market_assumptions(
        monthly_simple_returns=returns,
        annual_expected_simple_returns=mu,
        as_of=inputs["as_of"],
        data_provenance=inputs["data_provenance"],
        return_assumption_provenance=sources,
    )
    out = Path(output_dir) / f"market_assumptions_{inputs['as_of'].replace('-', '')}{suffix}.json"
    save_market_assumptions(result, out)
    return result


if __name__ == "__main__":
    try:
        r = run_pipeline()
    except (FileNotFoundError, ValueError) as e:
        print("가정 JSON을 만들지 않았습니다:", e)
        print("필요: data/market/monthly_returns.csv(실데이터) + assumptions_inputs.json(기대수익률 확정)")
    else:
        print(summarize(r))
        # 민감도 세트: 2025~2026 급변동 구간을 뺀 위험모수 (기대수익률은 동일)
        r2 = run_pipeline(history_end="2024-12-31", suffix="_pre2025")
        print("\n[민감도 세트 _pre2025]\n" + summarize(r2))
        # 하향 시나리오: 주식 기대수익률 6.00% (팀이 정한 비교값), 위험모수는 pre2025
        r3 = run_pipeline(history_end="2024-12-31", suffix="_pre2025_eq600",
                          mu_override={"equity_kr": 0.06},
                          override_note="주식이 기준 가정(8.46%)보다 덜 벌 때도 계획이 버티는지 보기 위해 팀이 정한 하향 비교값. 출처 기반 추정치 아님")
        print("\n[하향 시나리오 _pre2025_eq600]\n" + summarize(r3))
