import plotly.graph_objects as go
import streamlit as st

from core import ai, data as d, ui
from core.charts import rgba
from core.ui import BLUE, ORANGE, G600, G900

ui.head("우리 집", "우리 집 44년 미리 보기", "▶ 재생을 누르면 해마다 모아둔 돈이 어떻게 변하는지 보여드려요. 아래 막대를 움직이면 그해 가족 모습을 자세히 볼 수 있어요.")
ui.info("이 화면은 정해진 일만 보여드려요. 자녀 결혼·독립, 부모님 간병처럼 생길 수도 있는 일은 <b>만약에?</b>에서 확인하세요.")

EV = {2026: "지금: 부부 모두 직장에 다니고, 아들(27세)과 함께 살며 지원해요. 양가 어머니(83세)께는 매년 약 370만 원을 드려요.",
      2033: "배우자 은퇴! 퇴직금을 한 번에 받아 모아둬요.", 2034: "배우자는 연금을 기다리는 중. A씨 월급으로 생활해요.",
      2035: "A씨 은퇴! 퇴직금을 받아 약 1억 원을 '연금 기다리는 4년' 용으로 따로 떼어 둬요.",
      2036: "월급이 끊겼어요. 배우자 연금(69세)이 시작되지만 부족해서 모아둔 돈에서 꺼내 써요. 가장 빠듯한 해예요.",
      2037: "주택담보대출을 다 갚았어요. 나가는 돈이 줄어요.", 2038: "아직 A씨 연금 전. 모아둔 돈으로 버티는 마지막 해예요.",
      2039: "A씨 연금(70세) 시작! 늦게 받은 덕분에 연금이 36% 커서 다시 돈이 남기 시작해요.",
      2044: "아들이 45세가 되어 매달 드리던 지원이 끝나요.", 2069: "A씨 100세. 보통의 경우 약 5.2억 원이 남아요."}
SHORT = {2026: "지금", 2033: "배우자 은퇴", 2035: "A씨 은퇴", 2036: "월급 끊김 · 배우자 연금 시작", 2037: "대출 상환 끝",
         2039: "A씨 연금 시작", 2044: "아들 지원 끝", 2069: "A씨 100세"}


def status(y):
    return {"a": ("회사 다니는 중", "work") if y <= 2035 else ("은퇴 · 연금 기다리는 중", "wait") if y <= 2038 else ("국민연금 받는 중", "pen"),
            "s": ("회사 다니는 중", "work") if y <= 2033 else ("은퇴 · 연금 기다리는 중", "wait") if y <= 2035 else ("국민연금 받는 중", "pen"),
            "c": ("부모님 지원 받는 중", "sup") if y <= 2044 else ("지원 끝", "pen")}


f = d.D()["fan"]
ys, p50 = f["years"], f["p50"]
last = {}
lab = []
for y in ys:
    if y in SHORT:
        last = SHORT[y]
    lab.append(f"<b>{y}년</b> · A씨 {y - 1969}세 · 배우자 {y - 1967}세 · 아들 {y - 1999}세" + (f"  ·  {SHORT[y]}" if y in SHORT else ""))

with st.container(border=True):
    ui.title("모아둔 돈 (보통의 경우)", "억 원 · 오늘 가치")
    base = go.Scatter(x=ys, y=p50, fill="tozeroy", line=dict(color=BLUE, width=3), fillcolor=rgba(BLUE, .12), hovertemplate="%{x}년 %{y:.2f}억<extra></extra>")
    dot = lambda i: go.Scatter(x=[ys[i]], y=[p50[i]], mode="markers+text", text=[f"{p50[i]:.1f}억"], textposition="top center",
                               textfont=dict(size=15, color=G900), marker=dict(size=18, color=ORANGE, line=dict(color="white", width=3)), hoverinfo="skip")
    gap_lab = dict(text="연금 기다리는 4년", x=2037.5, y=0.99, xref="x", yref="paper", yanchor="top", bgcolor="rgba(255,255,255,0.85)", showarrow=False, font=dict(size=12, color="#B86E00"))
    ann = lambda i: [dict(text=lab[i], x=0, y=1.13, xref="paper", yref="paper", showarrow=False, xanchor="left", font=dict(size=15, color=G900)), gap_lab]
    fig = go.Figure(data=[base, dot(0)], frames=[go.Frame(data=[base, dot(i)], layout=go.Layout(annotations=ann(i)), name=str(y)) for i, y in enumerate(ys)])
    ui.style(fig, 400, legend=False, ysuf="억")
    ui.gap(fig, label=False, tint=True)
    fig.update_layout(annotations=ann(0), margin=dict(t=56, b=70),
                      updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.13, xanchor="left", yanchor="top", showactive=False,
                                        bgcolor=BLUE, font=dict(color="white", size=14), bordercolor=BLUE,
                                        buttons=[dict(label="▶ 재생", method="animate", args=[None, dict(frame=dict(duration=450, redraw=True), transition=dict(duration=250), fromcurrent=True)]),
                                                 dict(label="❚❚ 멈춤", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
                      sliders=[dict(active=0, x=.2, len=.8, y=-0.1, pad=dict(t=0), currentvalue=dict(visible=False), font=dict(color=G600, size=11),
                                    steps=[dict(label=str(y) if y % 5 == 1 or y in (2026, 2069) else "", method="animate",
                                                args=[[str(y)], dict(frame=dict(duration=0, redraw=True), mode="immediate")]) for y in ys])])
    fig.update_yaxes(range=[0, max(p50) * 1.25])
    ui.show(fig)
    ui.foot("주황 점선 사이 = 연금 기다리는 4년(2036~2039년). 월급이 끊기고 A씨 연금은 아직이라 모아둔 돈을 꺼내 쓰는 시기예요.")

with st.container(border=True):
    y = st.select_slider("자세히 볼 해", options=ys, value=st.session_state.get("life_y", 2036), key="life_y")
    s = status(y)
    P = [("A씨", "a", y - 1969, BLUE), ("배우자", "s", y - 1967, "#7A5AF8"), ("아들", "c", y - 1999, "#F25E9E")]
    ui.md("<div class='people'>" + "".join(
        f"<div class='person'><span class='av' style='background:{c}'>{n[:2]}</span><div><div class='nm'>{n} <span class='ag'>{age}세</span></div>"
        f"<span class='pill {s[k][1]}'>{s[k][0]}</span></div></div>" for n, k, age, c in P) + "</div>")
    r = d.cf(y)
    inc, out, ret, net = r["wage"] + r["pension"], -(r["living"] + r["family"] + r["housing"]), r["retire"], r["net"]
    ev = EV.get(y) or (f"모아둔 돈에서 약 {-net:,.0f}만 원을 꺼내 써요." if net < 0 else f"쓰고 남은 약 {net:,.0f}만 원을 모아요.")
    ui.md(f"<div class='event' key='{y}'>{ev}</div>")
    c1, c2 = st.columns([1, 2], gap="medium")
    with c1:
        ui.kpis([("모아둔 돈 (보통의 경우)", f"{p50[ys.index(y)]:.1f}<small>억 원</small>", "오늘 가치", True)], cols=1)
        rest = net - ret
        ui.md(f"<p class='say'>" + (f"퇴직금 <b>{ret:,.0f}만 원</b>은 따로 모아요. " if ret > 0 else "") +
              (f"올해는 <b>{-rest:,.0f}만 원 모자라요.</b>" if rest < 0 else f"올해는 <b>{rest:,.0f}만 원 남아요.</b>") + "</p>")
    with c2:
        mx = max(max(x["wage"] + x["pension"], -(x["living"] + x["family"] + x["housing"])) for x in d.D()["cashflow"])
        fig2 = go.Figure(go.Bar(y=["나간 돈", "들어온 돈"], x=[out, inc], orientation="h", marker_color=[ORANGE, BLUE],
                                text=[f"{out:,.0f}만", f"{inc:,.0f}만"], textposition="outside", hovertemplate="%{x:,.0f}만 원<extra></extra>"))
        ui.style(fig2, 170, legend=False)
        fig2.update_layout(margin=dict(l=80))
        fig2.update_xaxes(range=[0, mx * 1.15], showgrid=True)
        ui.show(fig2)

ai.ask_button("c_life", f"44년 미리 보기: 지금 {y}년을 보고 있음")
