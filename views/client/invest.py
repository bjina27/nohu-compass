import math

import streamlit as st

from core import ai, charts, data as d, risk, ui

ui.head("결정할 것", "모아둔 돈, 어떻게 굴릴까요?", "두 가지 방법을 비교했어요. 둘 다 목표(100세까지 지금 생활)는 지켜요.")
(va, ma), (vs, ms) = risk.use("a"), risk.use("s")
low, mock = min(va, vs) <= 22, ma or ms
with st.container(border=True):
    ui.md(f"<div class='ct'><b>✓ 두 분의 투자 성향: A씨 {d.band(va)} · 배우자 {d.band(vs)}{' (예시 답변)' if mock else ''}</b></div>")
    st.write("손실이 나는 게 불편한 편이라 **안정형**이 잘 맞아요. 성장형은 값이 출렁일 때 마음이 불편할 수 있어 권하지 않아요." if low else
             "적당한 위험은 받아들이는 편이지만, 목표를 지키는 데 주식이 꼭 필요하지 않아 **안정형**을 먼저 권해요. 성장형도 상담 후 선택할 수 있어요.")
    if mock:
        st.page_link("views/client/risk.py", label="내 성향 직접 알아보기 →")


def wave(vol):
    amp = min(22, vol * 1.2)
    pts = " ".join(f"L{x} {27 + amp * math.sin(x / 50 * 2 * math.pi):.1f}" for x in range(0, 264, 4))
    return f'<svg class="wave" viewBox="0 0 200 54" aria-hidden="true"><g><path d="M0 27 {pts}"/></g></svg>'


c1, c2 = st.columns(2, gap="medium")
for col, k, nm, bd, bullets in ((c1, "B00", "안정형 (B00)", ui.badge("추천", "ok"), ["예금 27% + 채권 73%, 주식 없음", "주가가 폭락해도 거의 흔들리지 않아요", "돈이 크게 불지는 않아요 (100세에 보통 5.2억)"]),
                                (c2, "B40", "성장형 (B40)", ui.badge("권하지 않음", "chk") if low else ui.badge("상담 후 선택", "mu"),
                                 ["예금 27% + 채권 44% + 주식 29%", "평균적으로 돈이 더 많이 남아요 (보통 8.6억)", "값이 안정형보다 2.5배 출렁여요"])):
    with col, st.container(border=True):
        ui.md(f"<div class='ct'><b>{nm}</b><span>{bd}</span></div>")
        ui.show(charts.donut(k, 170), key=f"cd{k}")
        ui.md(f"<b style='font-size:14px'>얼마나 흔들리나</b>{wave(d.strat(k)['vol'])}")
        st.markdown("\n".join(f"- {b}" for b in bullets))

with st.container(border=True):
    ui.title("100세에 남는 돈 비교", "억 원 · 오늘 가치")
    p, q = d.strat("B00"), d.strat("B40")
    ui.show(charts.pair_bars(["보통의 경우", "운이 나쁜 경우", "은퇴 직후 주가 폭락 + 운 나쁜 경우"],
                             [p["p50"], p["cvar"], d.stress("B00", "S1")["cvar"]], [q["p50"], q["cvar"], d.stress("B40", "S1")["cvar"]],
                             "안정형 (B00)", "성장형 (B40)", h=330))
    ui.easy("두 방법 모두 목표는 지켜요. 그래서 마음 편한 <b>안정형</b>을 먼저 권해요. 남는 돈을 더 키우고 싶고 손실을 견딜 수 있다면 성장형도 상담해 볼 수 있어요.", "그래서")

ai.ask_button("c_invest")
