import plotly.graph_objects as go
import streamlit as st

from core import ai, data as d, risk, ui
from core.ui import BLUE, G900

ui.head("나를 알기", "나의 투자 성향 알아보기", "돈을 어떻게 굴릴지 정하기 전에, 두 분이 손실을 얼마나 편하게 받아들이는지 먼저 알아볼게요. 13개 질문, 약 3분이면 돼요.")
BAND_TXT = {"낮음": "손실이 나는 게 많이 불편한 편이에요.", "평균보다 낮음": "수익보다 안정을 더 중시하는 편이에요.", "보통": "적당한 위험은 받아들이는 편이에요.",
            "평균보다 높음": "수익을 위해 위험을 꽤 감수하는 편이에요.", "높음": "큰 위험도 감수하는 편이에요."}

c1, c2 = st.columns([3, 2], gap="medium")
with c1, st.container(border=True):
    ui.title("질문")
    who = risk.survey("c")
with c2, st.container(border=True):
    ui.title("나의 성향")
    v, mock = risk.use(who)
    bands = d.D()["gl_bands"]
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v, number=dict(suffix="점", font=dict(size=40, color=G900)),
        gauge=dict(axis=dict(range=[13, 47], tickvals=[13, 19, 23, 29, 33, 47], tickfont=dict(size=11)),
                   bar=dict(color=G900, thickness=.18), bgcolor="white", borderwidth=0,
                   steps=[dict(range=[b["lo"] - (0 if i == 0 else 1), b["hi"]], color=c) for i, (b, c) in
                          enumerate(zip(bands, ["#E8F3FF", "#C9E2FF", "#90C2FF", "#5BA4FB", BLUE]))])))
    ui.style(fig, 250, legend=False)
    fig.update_layout(margin=dict(l=20, r=20, t=20, b=0))
    ui.show(fig)
    nm = "A씨" if who == "a" else "배우자"
    b = d.band(v)
    ui.md(f"<p class='say' style='text-align:center'><b>{nm} · {b}</b><br>{BAND_TXT.get(b, '')}</p>" +
          (f"<p style='text-align:center;font-size:13px;color:#8B95A1'>아직 {risk.score(who)[0]}/13문항 · 지금은 예시 답변({v}점)으로 보여드려요</p>" if mock else ""))

with st.container(border=True):
    ui.title("세 가지로 판단해요")
    (va, ma), (vs, ms) = risk.use("a"), risk.use("s")
    ui.md(f"""<div class="lights">
<div><span class="lamp g"></span><b style="min-width:70px">마음</b><span>A씨 {d.band(va)}, 배우자 {d.band(vs)} — {BAND_TXT.get(d.band(min(va, vs)), '')}{' (예시 답변 기준)' if ma or ms else ''}</span></div>
<div><span class="lamp g"></span><b style="min-width:70px">형편</b><span>보통 — 은퇴 직후 4년이 빠듯하지만, 손실이 나도 생활은 버틸 수 있어요.</span></div>
<div><span class="lamp g"></span><b style="min-width:70px">필요</b><span>높은 수익이 꼭 필요하지 않아요. 투자 수익이 없어도 돈이 바닥나지 않아요.</span></div></div>""")
    ui.easy("이 결과는 <b>돈 어떻게 굴릴까</b>에 반영돼요. 성향만으로 투자 비율을 자동으로 정하지는 않고, 최종 결정은 설계사와 상담에서 함께 확인해요.", "다음 단계")
    st.page_link("views/client/invest.py", label="돈 어떻게 굴릴까 →")

ai.ask_button("c_risk")
