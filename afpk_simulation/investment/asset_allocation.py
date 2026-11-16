# -*- coding: utf-8 -*-
"""STEP 4 — 자산배분 후보 생성 및 평가 (컷오프 없음). investment/asset_allocation.py

팀 설계(STEP4 문서 3.1~3.3)에 따라:
  - 비상자금(필수지출 3개월 / 6개월)을 예적금으로 먼저 확보
  - 잔여 투자금의 주식 비중 0~100% (10%p), 나머지 채권  → 22개 후보
  - 기본 제약(비상자금 확보, 고객 거부조건)만 확인하고 위험지표 등급으로 탈락시키지 않음
  - 위험수용성·위험감수능력·위험필요도는 '참고 정보'로만 기록

출력:
  outputs/portfolios/step4_candidates.csv    사람이 보는 평가표 (22개 × 주식 시나리오 2개)
  outputs/portfolios/step4_strategies.json   몬테카를로가 읽는 후보 목록 + 시장가정 파일 연결 정보

실행:  python -m investment.asset_allocation   (저장소 루트에서)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MARKET = ROOT / "data" / "market"
OUT = ROOT / "outputs" / "portfolios"

ASSETS = ("cash", "bond_kr", "equity_kr")

# ---- 가구 입력 (출처: afpk_simulation/config.py, interfaces/housing.py, 위험감수능력 문서) ----
INITIAL_FINANCIAL_ASSETS = 70_130_000      # 2026년 초 금융자산 (주택·자동차 제외)
MONTHLY_MIN_LIVING = 2_166_000             # 최소생활비 (2026년 가치)
MONTHLY_MORTGAGE = 988_029                 # 주담대 원리금 (4.5%, 12년 원리금균등), 생활비와 별도 지출
EMERGENCY_MONTHS = (3, 6)                  # 비교 시나리오 A, B (FINRA·Vanguard 3~6개월 출발 기준)
EQUITY_STEPS = tuple(range(0, 101, 10))    # 잔여 투자금 중 주식 비중 (%)

# ---- 시장가정 시나리오 ----
MARKET_SCENARIOS = {
    "base_846": {"label": "기준 (주식 8.46%)", "file": "market_assumptions_20261031_pre2025.json"},
    "down_600": {"label": "하향 (주식 6.00%, 위험프리미엄 약 절반)", "file": "market_assumptions_20261031_pre2025_eq600.json"},
}

# ---- 참고 지표 입력 ----
STRESS_EQUITY_LOSS = 1 - 938.75 / 2064.85   # 2007-10~2008-10 코스피 하락률 ≈ 54.54% (위험감수능력 모듈과 동일)
STRESS_BOND_LOSS = 0.0                      # 위험감수능력 모듈 가정. 같은 기간 국고채프라임 총수익지수는 +7.5%
ALM_FLOOR_2026 = 0                          # risk_capacity.assess_risk_capacity 실행값: 2026년 초 최소·적정생활비 바닥 모두 0원
CFA_CAPACITY_2026 = "보통 — 비상시 외부 소득·자산 '있으나 불충분'(페르소나 가정, 실제 조사로 검증된 값 아님). C48 공백기 2036~2039 포함 2026~2064 보통"   # risk_capacity.classify_cfa: outside_resources를 '충분함 아님'으로 둔 판정 (팀 결정 2026-11-16)
RISK_NEED = {"label": "낮음", "required_return_plan": 0.0, "required_growth_share": 0.0,
             "note": "risk_need.assess_risk_need 실행값(현행 엔진, C48). 계획지출 전체·최소생활비 기준 모두 요구수익률 0%"
                     "(투자수익이 없어도 금융자산이 바닥나지 않음). 세후 시장가정(예적금 2.81%·채권 3.23%·주식 8.30%). "
                     "기존 2.58%는 11-15 구버전 기록으로 재현 불가하여 제외(팀원 동의). "
                     "비상자금 3·6개월(현금 13.5%·27%) 모두 필요 성장자산 0%(방어자산·현금만으로 충분)"}
RISK_MODULE_RUN = ("2026-11-16 재계산: scripts/risk_profile_c48.py(risk_profile 패키지 = 팀원 모듈 원본) — "
                   "최종안 C48(A씨 70·배우자 69) 기본 경로, 퇴직급여 일시금, 투자 미연결, 세후 시장가정; "
                   "CFA 유동성=계획 장부, ALM 바닥=최소 장부(양가 어머니 지원만)")
GL_SCORES = {"A씨": 23, "배우자": 26}         # 둘 다 '보통'(23~28점); A씨는 구간 하한

N_DRAWS = 400_000
SEED = 20261115


def build_candidates() -> list[dict]:
    monthly_essential = MONTHLY_MIN_LIVING + MONTHLY_MORTGAGE
    cands = []
    for months in EMERGENCY_MONTHS:
        cash_amt = monthly_essential * months
        if cash_amt > INITIAL_FINANCIAL_ASSETS:
            raise ValueError("비상자금이 금융자산보다 큽니다.")
        c = cash_amt / INITIAL_FINANCIAL_ASSETS
        scen = "A" if months == 3 else "B"
        for k in EQUITY_STEPS:
            e = (1 - c) * k / 100
            b = (1 - c) - e
            cands.append({
                "id": f"{scen}{k:02d}" if k < 100 else f"{scen}100",
                "emergency_months": months,
                "equity_share_of_remainder": k / 100,
                "weights": {"cash": c, "bond_kr": b, "equity_kr": e},
            })
    return cands


def load_market(fname: str):
    d = json.loads((MARKET / fname).read_text(encoding="utf-8"))
    if d["assets"] != list(ASSETS):
        raise ValueError("자산 순서 불일치")
    return (np.array(d["annual_expected_simple_returns"]), np.array(d["annual_log_means"]),
            np.array(d["annual_log_cov"]))


def evaluate(cands: list[dict]) -> pd.DataFrame:
    A = INITIAL_FINANCIAL_ASSETS
    rows = []
    for skey, sc in MARKET_SCENARIOS.items():
        mu, m, S = load_market(sc["file"])
        R = np.exp(np.random.default_rng(SEED).multivariate_normal(m, S, size=N_DRAWS, method="cholesky")) - 1
        for cd in cands:
            w = np.array([cd["weights"][a] for a in ASSETS])
            rp = R @ w                                   # 포트폴리오 = 자산별 단순수익률 가중합
            var5 = np.quantile(rp, 0.05)
            cvar5 = rp[rp <= var5].mean()
            shock_assets = A * (1 - w[2] * STRESS_EQUITY_LOSS - w[1] * STRESS_BOND_LOSS)
            rows.append({
                "주식시나리오": sc["label"], "시나리오키": skey, "후보": cd["id"],
                "비상자금": f"{cd['emergency_months']}개월", "잔여금중주식%": round(cd["equity_share_of_remainder"] * 100),
                "예적금%": w[0] * 100, "채권%": w[1] * 100, "주식%": w[2] * 100,
                "예적금(원)": round(A * w[0]), "채권(원)": round(A * w[1]), "주식(원)": round(A * w[2]),
                "기대수익률%": w @ mu * 100, "변동성%": rp.std() * 100, "1년손실확률%": (rp < 0).mean() * 100,
                "VaR5%": var5 * 100, "VaR5(원)": round(A * var5), "CVaR5%": cvar5 * 100, "CVaR5(원)": round(A * cvar5),
                "2008형충격손실(원)": round(A - shock_assets),
                "기본제약_비상자금": "충족", "기본제약_고객거부조건": "해당없음(페르소나에 거부조건 없음)",
                "STEP5대상": "예",
                "참고_위험수용성": f"A씨 {GL_SCORES['A씨']}점·배우자 {GL_SCORES['배우자']}점(보통). 1년 VaR {var5*100:.1f}%({A*var5/1e4:,.0f}만원) 감내 여부 상담 확인",
                "참고_위험감수능력": ("CFA {}; 2008형 충격 후 금융자산 {:,.0f}만원 ≥ 생활비 바닥 {:,.0f}원 → 유지".format(CFA_CAPACITY_2026, shock_assets / 1e4, ALM_FLOOR_2026)
                                 if shock_assets >= ALM_FLOOR_2026 else "2008형 충격 후 생활비 바닥 미달"),
                "참고_위험필요도": "낮음(필요 성장자산 0%, 계획지출 요구수익률 0%). 이 후보 주식 {:.1f}%는 필요 수준 이상".format(w[2] * 100) if w[2] > 0 else "낮음(필요 성장자산 0%). 필요 수준과 일치",
            })
    return pd.DataFrame(rows)


def strategies_json(cands: list[dict]) -> dict:
    return {
        "as_of": "2026-10-31",
        "created_by": "investment/asset_allocation.py",
        "asset_order": list(ASSETS),
        "initial_financial_assets": INITIAL_FINANCIAL_ASSETS,
        "emergency_fund_basis": {"monthly_min_living": MONTHLY_MIN_LIVING, "monthly_mortgage": MONTHLY_MORTGAGE,
                                 "monthly_essential": MONTHLY_MIN_LIVING + MONTHLY_MORTGAGE, "months": list(EMERGENCY_MONTHS)},
        "market_scenarios": {k: {"label": v["label"], "file": f"data/market/{v['file']}"} for k, v in MARKET_SCENARIOS.items()},
        "risk_inputs_status": {
            "risk_tolerance": {"value": GL_SCORES, "status": "모의상담 설정값을 코드에 직접 입력. 최종 추천 시 확정된 G&L 평가 결과와 연결 필요"},
            "risk_capacity": {"cfa_2026": CFA_CAPACITY_2026, "alm_floor_2026_min_and_adequate": ALM_FLOOR_2026,
                              "stress_reference_growth_share_2026": 1.0,
                              "status": "risk_capacity 모듈 실행값(" + RISK_MODULE_RUN + "). CFA 보통 확정: 외부 재원 '충분함' 미확인을 보수적 페르소나 가정으로 둠(팀 결정 2026-11-16)"},
            "risk_need": dict(RISK_NEED, status="risk_need 모듈 실행값(" + RISK_MODULE_RUN + ")"),
        },
        "screening": "컷오프 없음. 기본 제약(비상자금 확보·고객 거부조건)만 확인 → 22개 전부 STEP 5 대상",
        "monte_carlo_contract": {
            "weights_unit": "소수, 합 1 (전체 금융자산 기준)",
            "portfolio_return": "연 포트폴리오 단순수익률 = sum_i w_i × R_i, R_i = exp(x_i) − 1, x ~ MVN(annual_log_means, annual_log_cov)",
            "rebalancing": "매년 초 목표비중으로 리밸런싱 가정 (portfolio_engine에서 변경 가능)",
            "emergency_fund": "비상자금은 예적금 비중에 포함된 금액. 생활비 바닥 등에서 다시 차감하지 않음",
            "fees_taxes": "시장 수익률은 세전·보수 전. 보수는 monte_carlo, 세금은 portfolio_engine에서 처리",
            "same_paths": "공정 비교를 위해 22개 후보는 같은 시나리오 안에서 동일한 난수 경로(같은 seed)를 사용",
        },
        "strategies": [{"id": c["id"], "emergency_months": c["emergency_months"],
                        "equity_share_of_remainder": c["equity_share_of_remainder"],
                        "weights": [round(c["weights"][a], 10) for a in ASSETS]} for c in cands],
    }


def main():
    cands = build_candidates()
    df = evaluate(cands)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "step4_candidates.csv", index=False, encoding="utf-8-sig", float_format="%.2f")
    (OUT / "step4_strategies.json").write_text(json.dumps(strategies_json(cands), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"후보 {len(cands)}개 × 시장 시나리오 {len(MARKET_SCENARIOS)}개 = {len(df)}행 저장")
    return df


if __name__ == "__main__":
    main()
