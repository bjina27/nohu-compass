import plotly.graph_objects as go
import streamlit as st

from core import ai, data as d, ui
from core.ui import BLUE, GREEN, ORANGE

ui.head("결정할 것", "만약에 이런 일이 생기면?", "걱정되는 일을 골라 보세요. 안정형(B00) + 추천 연금 시기 기준입니다.")
OPT = {"S1": "📉 주가 폭락 · 은퇴 직후 반토막", "S2": "🔥 물가 급등 · 5년간 매년 5%", "S3b": "💍 자녀 일이 몰리면 · 결혼·독립 비용", "S4b": "⚡ 한꺼번에 · 폭락 + 자녀 일"}
SAY = {"S1": "안정형은 주식이 없어서 주가가 폭락해도 거의 영향이 없어요.",
       "S2": "물가가 몇 년 크게 오르는 게 유일한 약점이에요. 하지만 '빠듯하면 잠시 아껴 쓰기' 규칙을 정해두면 지금 생활도 지킬 수 있어요.",
       "S3b": "자녀 결혼·독립 비용이 가장 나쁜 때 몰려도, 남는 돈이 줄 뿐 생활은 지켜져요.",
       "S4b": "주가 폭락과 자녀 일이 한꺼번에 와도 생활은 지켜져요."}
sel = st.segmented_control("상황", list(OPT), default="S1", format_func=OPT.get, key="c_ws", label_visibility="collapsed", width="stretch") or "S1"
b0, bx = d.stress("B00", "S0"), d.stress("B00", sel)

c1, c2 = st.columns([3, 2], gap="medium")
with c1, st.container(border=True):
    ui.title("운이 나쁜 경우 100세에 남는 돈", "억 원")
    v = [b0["cvar"], bx["cvar"]]
    fig = go.Figure(go.Bar(x=["평소", "이 일이 생기면"], y=v, marker_color=[BLUE, ORANGE], text=[f"{x:.1f}억" for x in v],
                           textposition="outside", textfont=dict(size=16), hovertemplate="%{y:.2f}억<extra></extra>"))
    ui.style(fig, 280, legend=False, ysuf="억")
    fig.update_yaxes(range=[0, 4.3])
    ui.show(fig)
    diff = bx["cvar"] - b0["cvar"]
    ui.md(f"<p class='say fadeup'>{SAY[sel]} " + ("남는 돈도 <b>거의 그대로</b>예요." if abs(diff) < .05 else f"운이 나쁜 경우 남는 돈이 <b>{abs(diff):.1f}억 원 {'줄어요' if diff < 0 else '늘어요'}</b>.") + "</p>")
with c2, st.container(border=True):
    ui.title("생활은 괜찮을까?")
    sh = bx["short"]
    rows = [("g", "<b>기본 생활</b> — 지켜져요"), ("y" if sh > 0 else "g", f"<b>지금 생활</b> — {'빠듯한 미래가 ' + d.per100(sh) if sh > 0 else '지켜져요'}")]
    if sel == "S2":
        rows.append(("g", f"<b>아껴 쓰기 규칙을 쓰면</b> — 빠듯한 미래 {d.per100(d.guard('S2', 'living')['short'])}"))
    ui.md("<div class='lights'>" + "".join(f"<div><span class='lamp {k}'></span><span>{t}</span></div>" for k, t in rows) + "</div>")

with st.container(border=True):
    ui.title("생활비를 바꾸면?", "운이 나쁜 경우 100세에 남는 돈")
    lv = next(r for r in d.D()["tornado"]["rows"] if "생활비" in r["name"])
    labs = [f"생활비 {lv['hi']}", "지금 생활비", f"생활비 {lv['lo']}"]
    vals = [3.30 + lv["d_high"], 3.30, 3.30 + lv["d_low"]]
    fig = go.Figure(go.Bar(y=labs, x=vals, orientation="h", marker_color=[ORANGE, BLUE, GREEN], text=[f"{x:.1f}억" for x in vals],
                           textposition="outside", textfont=dict(size=15), hovertemplate="%{x:.2f}억<extra></extra>"))
    ui.style(fig, 230, legend=False)
    fig.update_layout(margin=dict(l=130))
    fig.update_xaxes(range=[0, 6], ticksuffix="억", showgrid=True)
    ui.show(fig)
    ui.easy("주가나 물가보다 <b>매달 쓰는 생활비</b>가 노후를 더 크게 바꿔요.", "알아두세요")

ai.ask_button("c_whatif", f"만약에: 지금 '{OPT[sel]}' 선택 중")
