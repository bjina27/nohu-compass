"""생애사건 직접 지정(AI 상담·스트레스 테스트용).

지정하지 않은 사건은 기존처럼 master seed의 확률 추첨 결과를 그대로 쓴다.
지정한 항목만 덮어쓴다. 어떤 옵션도 주지 않으면 결과는 기존과 동일하다.

자녀 child_overrides
    marriage_year        : 정수 연도 | "never" | None(확률 그대로)
    independence_year    : 정수 연도 | "never" | None
    marriage_support     : 결혼 지원 목표 금액(원) | None(통계 분포)
    independence_support : 독립 지원 목표 금액(원) | None(통계 분포)
    amount_basis         : "nominal"(그해 실제 금액, 기본) | "2026"(2026년 가치)
  - 연도를 하나라도 지정하면 지정하지 않은 사건은 '일어나지 않음'으로 본다.
    (예: "내후년 결혼"만 말하면 그 전 독립은 없는 것으로 처리)
  - 연도를 지정하지 않고 금액만 주면 사건 시기는 확률 그대로, 금액만 바뀐다.
  - 금액은 '목표'이며 그해 지급능력 상한이 그대로 적용된다(실지급액은 결과 행에 기록).
  - 연도 범위: 아들 27~44세(2026~2043년). 독립은 결혼보다 먼저여야 한다.

부모 parent_overrides
    a_mother_stroke_year        : 정수 연도 | "never" | None
    spouse_mother_ltc_entry_year: 정수 연도 | "never" | None
  - 연도 범위: 2026년 ~ 어머니 99세 연도(2042년). 100세부터는 비용이 0이라 지정 불가.

재취업 reemployment_overrides
    a_duration_years / spouse_duration_years : 0(재취업 안 함) ~ 10 | None(확률 그대로)
    a_monthly / spouse_monthly               : 재취업 월소득(2026년 가치, 원) | None(기본값)
  - 재취업은 67세부터 시작한다(엔진 규칙). 국민연금 세금 계산도 같은 상태를 쓴다.
"""
from __future__ import annotations

import copy
from dataclasses import replace

from engine import inflation_factor

NEVER = "never"


def _year_or_none(value, name, lo, hi):
    if value is None or value == NEVER:
        return value
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name}는 정수 연도, 'never', None 중 하나여야 합니다.")
    if not lo <= value <= hi:
        raise ValueError(f"{name}={value}는 허용 범위({lo}~{hi}년) 밖입니다.")
    return value


def _amount(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name}는 0 이상의 금액이어야 합니다.")
    return int(round(value))


def apply_child_overrides(sampled, overrides, config):
    o = dict(overrides or {})
    unknown = set(o) - {"marriage_year", "independence_year", "marriage_support",
                        "independence_support", "amount_basis"}
    if unknown:
        raise ValueError(f"알 수 없는 자녀 옵션: {sorted(unknown)}")
    basis = o.get("amount_basis", "nominal")
    if basis not in ("nominal", "2026"):
        raise ValueError("amount_basis는 'nominal' 또는 '2026'이어야 합니다.")
    birth = config.start_year - config.son_age_2026
    lo, hi = birth + 27, birth + 44
    m = _year_or_none(o.get("marriage_year"), "marriage_year", lo, hi)
    i = _year_or_none(o.get("independence_year"), "independence_year", lo, hi)
    m_amt = _amount(o.get("marriage_support"), "marriage_support")
    i_amt = _amount(o.get("independence_support"), "independence_support")

    state = copy.deepcopy(sampled)
    if m is not None or i is not None:
        m_year = None if m in (None, NEVER) else m
        i_year = None if i in (None, NEVER) else i
        if m_year is not None and i_year is not None and i_year >= m_year:
            raise ValueError("독립 연도는 결혼 연도보다 앞서야 합니다(결혼과 동시 독립은 결혼으로 처리).")
        first = min(y for y in (m_year, i_year) if y is not None) if (m_year or i_year) else None
        state.update({
            "independence_year": i_year,
            "marriage_year": m_year,
            "first_exit_year": first,
            "first_exit_type": (None if first is None else
                                "simple_independence" if first == i_year else "marriage_from_cohabitation"),
            "final_status": ("married" if m_year else "independent_unmarried" if i_year
                             else "cohabiting_unmarried"),
            "user_specified_timing": True,
        })
        if m_year and not state.get("marriage_support_bracket"):
            state["marriage_support_bracket"] = {"label": "none", "representative_amount": 0}

    def to_nominal(amount, year):
        if amount is None or year is None:
            return None
        return amount if basis == "nominal" else round(amount * inflation_factor(year, config))

    state["marriage_support_override_nominal"] = to_nominal(m_amt, state.get("marriage_year"))
    state["independence_support_override_nominal"] = to_nominal(i_amt, state.get("independence_year"))
    return state


def apply_parent_overrides(sampled, overrides, config, scenario):
    o = dict(overrides or {})
    unknown = set(o) - {"a_mother_stroke_year", "spouse_mother_ltc_entry_year"}
    if unknown:
        raise ValueError(f"알 수 없는 부모 옵션: {sorted(unknown)}")
    last = config.start_year + (scenario.parent_cashflow_end_age - 1 - scenario.parent_mother_age_2026)
    state = dict(sampled)
    for key in ("a_mother_stroke_year", "spouse_mother_ltc_entry_year"):
        if key in o:
            v = _year_or_none(o[key], key, config.start_year, last)
            if v is not None:
                state[key] = None if v == NEVER else v
    return state


def apply_reemployment_overrides(sampled, overrides, scenario):
    o = dict(overrides or {})
    unknown = set(o) - {"a_duration_years", "spouse_duration_years", "a_monthly", "spouse_monthly"}
    if unknown:
        raise ValueError(f"알 수 없는 재취업 옵션: {sorted(unknown)}")
    state = copy.deepcopy(sampled)
    for who in ("a", "spouse"):
        d = o.get(f"{who}_duration_years")
        if d is None:
            continue
        if isinstance(d, bool) or not isinstance(d, int) or not 0 <= d <= 10:
            raise ValueError(f"{who}_duration_years는 0~10 정수여야 합니다.")
        state[who] = {**state[who], "success": d > 0, "duration_years": d,
                      "user_specified": True}
    changes = {}
    for who, field in (("a", "a_reemployment_monthly"), ("spouse", "spouse_reemployment_monthly")):
        v = _amount(o.get(f"{who}_monthly"), f"{who}_monthly")
        if v is not None:
            changes[field] = v
    return state, (replace(scenario, **changes) if changes else scenario)
