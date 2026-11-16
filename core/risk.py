"""위험 성향(G&L 설문·CFA·필요도) 상태와 판정. 설계사·고객 화면이 같은 응답을 공유한다.

원칙: 등급은 판정(확정/조건부/보류)에만 쓰고 주식 비중으로 자동 변환하지 않는다.
"""
import streamlit as st

from core import data as d

ORDER = {"낮음": 0, "보통": 1, "높음": 2}


def init():
    ss = st.session_state
    ss.setdefault("gl", {"a": {}, "s": {}})       # 문항번호 -> 선택지 index
    ss.setdefault("glq", {"a": 0, "s": 0})        # 보고 있는 문항 index
    ss.setdefault("outside", "some")


def score(who):
    init()
    items = {it["n"]: it for it in d.D()["gl_items"]}
    a = st.session_state.gl[who]
    return len(a), sum(items[n]["o"][j]["s"] for n, j in a.items())


def use(who):
    """13문항을 다 답했으면 실제 점수, 아니면 페르소나 모의응답."""
    n, s = score(who)
    return (s, False) if n == 13 else (d.MOCK[who], True)


def min_capacity(outside=None):
    outside = outside or st.session_state.get("outside", "some")
    if outside == "unknown":
        return None
    ys = [y for y in d.D()["cfa"][outside] if y["y"] < 2065 and y["r"] in ORDER]
    return min(ORDER[y["r"]] for y in ys) if ys else None


def judge(eq_share):
    """eq_share: 비상자금을 뺀 나머지 중 주식 비율(%)."""
    outside = st.session_state.get("outside", "some")
    if outside == "unknown":
        return "판정 보류", "chk", "외부 재원을 확인해야 감수능력이 정해집니다."
    if eq_share == 0:
        return "수학적 후보 · 충돌 없음", "ok", "필요도가 감수능력 이내이고 주식이 없습니다."
    if min_capacity(outside) == 0:
        return "보류", "chk", "감수능력이 낮은 해가 있는데 주식이 들어간 전략입니다."
    if any(use(w)[0] <= 22 for w in ("a", "s")):
        return "조건부 · 상담 필요", "chk", "수용성이 평균보다 낮습니다. 손실 한도를 확인하세요."
    return "조건부 대안", "mu", "충돌은 없지만 수학적 후보가 아닙니다."


def survey(prefix="p"):
    """G&L 13문항을 한 문항씩. 설계사·고객 화면 공용."""
    init()
    ss = st.session_state
    items = d.D()["gl_items"]
    who_lbl = st.segmented_control("응답자", ["A씨", "배우자"], default="A씨", key=f"{prefix}_who", label_visibility="collapsed")
    who = "s" if who_lbl == "배우자" else "a"
    ans = ss.gl[who]
    i = ss.glq[who]
    it = items[i]
    n, s = score(who)
    st.progress(n / 13, text=f"응답 {n} / 13")

    def save(w=who, num=it["n"], k=f"{prefix}_r_{who}_{it['n']}"):
        v = ss.get(k)
        if v is not None:
            ss.gl[w][num] = v
            if ss.glq[w] < 12:
                ss.glq[w] += 1

    st.radio(f"**Q{it['n']}. {it['q']}**", options=list(range(len(it["o"]))), format_func=lambda j: it["o"][j]["t"],
             index=ans.get(it["n"]), key=f"{prefix}_r_{who}_{it['n']}", on_change=save)
    c1, c2, c3 = st.columns(3)
    if c1.button("← 이전", key=f"{prefix}_prev", disabled=i == 0, width="stretch"):
        ss.glq[who] -= 1
        st.rerun()
    if c2.button("다음 →", key=f"{prefix}_next", disabled=i == 12, width="stretch"):
        ss.glq[who] += 1
        st.rerun()
    if c3.button("처음부터", key=f"{prefix}_reset", width="stretch"):
        ss.gl = {"a": {}, "s": {}}
        ss.glq = {"a": 0, "s": 0}
        st.rerun()
    nm = "A씨" if who == "a" else "배우자"
    if n < 13:
        st.caption(f"13문항을 다 답하면 점수가 나옵니다. 그 전에는 {nm} 페르소나 모의응답 {d.MOCK[who]}점({d.band(d.MOCK[who])})으로 평가합니다.")
    else:
        st.caption(f"{nm} 총점 {s}점 · {d.band(s)} (13–47점)")
    return who
