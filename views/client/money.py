import plotly.graph_objects as go
import streamlit as st

from core import ai, data as d, ui
from core.ui import BLUE, ORANGE, PINK, YELLOW

ui.head("우리 집", "우리 집 돈의 흐름", "인생을 세 시기로 나눠, 1년에 평균 얼마가 들어오고 나가는지 봤어요. (오늘 돈 가치 기준)")
rows = d.D()["cashflow"]
avg = lambda xs: sum(xs) / len(xs)
ph = []
for n, r, a, b in (("일하는 시기", "2026~2035", 2026, 2035), ("연금 기다리는 4년", "2036~2039", 2036, 2039), ("연금 받는 시기", "2040~2069", 2040, 2069)):
    rs = [x for x in rows if a <= x["year"] <= b]
    ph.append(dict(n=f"{n}<br><span style='font-size:12px'>{r}</span>", inc=avg([x["wage"] + x["pension"] for x in rs]), out=avg([-(x["living"] + x["family"] + x["housing"]) for x in rs])))

with st.container(border=True):
    ui.title("시기별 1년 평균 수입과 지출", "만 원")
    fig = go.Figure([go.Bar(name="들어오는 돈 (월급·연금)", x=[p["n"] for p in ph], y=[p["inc"] for p in ph], marker_color=BLUE,
                            text=[f"{p['inc']:,.0f}만" for p in ph], textposition="outside", hovertemplate="1년 %{y:,.0f}만 원<extra></extra>"),
                     go.Bar(name="나가는 돈", x=[p["n"] for p in ph], y=[p["out"] for p in ph], marker_color=ORANGE,
                            text=[f"{p['out']:,.0f}만" for p in ph], textposition="outside", hovertemplate="1년 %{y:,.0f}만 원<extra></extra>")])
    ui.style(fig, 360)
    fig.update_yaxes(range=[0, max(max(p["inc"], p["out"]) for p in ph) * 1.2])
    ui.show(fig)
    w, g, l = ph
    ui.easy(f"일할 때는 1년에 약 {w['inc'] - w['out']:,.0f}만 원이 남아요. 하지만 <b>연금을 기다리는 4년</b>은 1년에 평균 <b>{g['out'] - g['inc']:,.0f}만 원</b>이 모자라 모아둔 돈에서 꺼내 써요. "
            + (f"연금을 받기 시작하면 다시 1년에 약 {l['inc'] - l['out']:,.0f}만 원이 남아요." if l["inc"] >= l["out"] else "연금을 받기 시작하면 거의 맞아떨어져요."), "핵심")

c1, c2 = st.columns(2, gap="medium")
with c1, st.container(border=True):
    ui.title("나가는 돈은 어디로?", "44년 합계")
    parts = [("생활비", -sum(x["living"] for x in rows), ORANGE), ("가족 지원 (어머니·아들)", -sum(x["family"] for x in rows), PINK), ("주택대출 상환", -sum(x["housing"] for x in rows), YELLOW)]
    tot = sum(p[1] for p in parts)
    fig = go.Figure(go.Pie(labels=[f"{p[0]} {p[1] / tot * 100:.0f}%" for p in parts], values=[p[1] for p in parts], hole=.6, sort=False,
                           marker=dict(colors=[p[2] for p in parts], line=dict(color="white", width=2)), textinfo="none",
                           customdata=[p[1] / 10000 for p in parts], hovertemplate="%{label}<br>약 %{customdata:.1f}억 원<extra></extra>"))
    ui.style(fig, 260)
    fig.update_layout(legend=dict(orientation="v", x=1, y=.5, yanchor="middle"))
    ui.show(fig)
with c2, st.container(border=True):
    ui.title("그래서 미리 준비할 것")
    ui.kpis([("은퇴할 때 따로 떼어 둘 돈", "약 1<small>억 원</small>", "오늘 가치 약 8천만 원 · 퇴직금으로 마련", True)], cols=1)
    st.markdown("- 예금·채권처럼 원금이 잘 안 흔들리는 곳에 둬요.\n- 배우자 연금(2036년), 대출 끝(2037년), A씨 연금(2039년) 순서로 빈틈이 메워져요.\n- A씨 연금이 나오면 다시 매년 돈이 남아요.")
    st.page_link("views/client/life.py", label="해마다 보기 →")

ai.ask_button("c_money", "돈의 흐름: 시기별 평균 수입·지출, 공백기 4년 연평균 부족액")
