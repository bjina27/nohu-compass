import plotly.graph_objects as go
import streamlit as st

from core import ai, data as d, ui
from core.ui import BLUE, BLUE_L, ORANGE

ui.head("결정할 것", "국민연금, 언제 받는 게 좋을까요?", "세 가지 중 하나를 눌러 보세요. 매달 받는 연금과 100세에 남는 돈이 바뀝니다.")
LBL = {"early": "일찍 받기 (A씨 60세 · 배우자 59세)", "normal": "제때 받기 (A씨 65세 · 배우자 64세)", "late": "늦게 받기 · 추천 (A씨 70세 · 배우자 69세)"}
sel = st.segmented_control("수령 시기", list(LBL), default="late", format_func=LBL.get, key="c_pen", label_visibility="collapsed", width="stretch") or "late"
a, s, l, size = d.PEN[sel]
c = d.cell(a, s)
keys = list(d.PEN)

c1, c2 = st.columns(2, gap="medium")
with c1, st.container(border=True):
    ui.title("매달 받는 연금 크기", "제때 = 100")
    fig = go.Figure(go.Bar(x=[d.PEN[k][2] + " 받기" for k in keys], y=[d.PEN[k][3] for k in keys],
                           marker_color=[BLUE if k == sel else BLUE_L for k in keys], text=[d.PEN[k][3] for k in keys], textposition="outside",
                           textfont=dict(size=16), hovertemplate="제때를 100으로 볼 때 %{y}<extra></extra>"))
    ui.style(fig, 280, legend=False)
    fig.update_yaxes(range=[0, 160])
    ui.show(fig)
    ui.foot("법으로 정해진 비율: 1년 일찍 받을 때마다 6% 줄고, 1년 늦출 때마다 7.2% 늘어요. 세금 떼기 전 금액 기준이라, 실제로 손에 쥐는 금액의 차이는 이보다 조금 작아요.")
with c2, st.container(border=True):
    ui.title("100세에 남는 돈", "억 원 · 오늘 가치")
    v = [c["p50"], max(0, c["cvar"])]
    fig = go.Figure(go.Bar(x=["보통의 경우", "운이 나쁜 경우"], y=v, marker_color=[BLUE, ORANGE], text=[f"{x:.1f}억" for x in v],
                           textposition="outside", textfont=dict(size=16), hovertemplate="%{y:.2f}억<extra></extra>"))
    ui.style(fig, 280, legend=False, ysuf="억")
    fig.update_yaxes(range=[0, 6.5])
    ui.show(fig)

bad = "거의 남지 않아요" if c["cvar"] <= .05 else f"{c['cvar']:.1f}억 원이 남아요"
ui.md(f"<p class='say fadeup'><b>{l} 받으면</b> (A씨 {a}세 · 배우자 {s}세) 매달 연금이 제때의 <b>{size}%</b>예요. 100세에 보통 <b>{c['p50']:.1f}억 원</b>, 운이 나쁘면 <b>{bad}</b>. "
      f"지금처럼 생활하지 못하는 미래는 <b>{d.per100(c['short'])}</b>이에요.</p>")
ui.easy("늦게 받으면 처음 몇 년은 손해 같지만, 오래 사실수록 유리해요. 이 계산은 두 분이 100세까지 사신다고 가정했어요.", "알아두세요")

ai.ask_button("c_pension", f"연금 시기: 지금 '{LBL[sel]}' 선택 중")
