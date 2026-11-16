import streamlit as st

from core import charts, data as d, ui

ui.head("6단계 · 점검 ①", "위기 테스트", "은퇴 직후 폭락, 5년 고물가, 가족 사건을 겹쳐 넣기")
market = st.selectbox("시장", list(d.MARKETS), format_func=d.MARKETS.get, key="st_k")
c1, c2 = st.columns(2, gap="medium")
with c1, st.container(border=True):
    ui.title("시나리오별 나쁜 경우 자산", "하위 5% 평균, 억 원")
    ui.show(charts.stress_bars(market))
with c2, st.container(border=True):
    ui.title("고물가에서 가드레일 효과", "S2 · 지금 생활 유지 실패 확률")
    ui.show(charts.guard_bars())

with st.container(border=True):
    ui.title("가드레일 비교표")
    gs = ["none", "bridge", "living", "both"]
    mx = max(d.guard("S2", g)["short"] for g in gs) or 1
    rows = []
    for g in gs:
        a, b = d.guard("S2", g), d.guard("S0", g)
        rows.append([d.GUARD_NAMES[g] + (" " + ui.badge("추천") if g == "living" else ""),
                     f"<span class='bar' style='width:{max(2, a['short'] / mx * 70):.0f}px'></span>{a['short']:.2f}%", f"{a['cut']:.1f}%", f"{b['paid']:,}만 원"])
    ui.table(["규칙", "고물가 실패", "생활비 줄인 미래", "평상시 자녀 지원(평균)"], rows, num=(2, 3))
    ui.easy("물가가 몇 년 크게 오르는 경우가 유일한 약점입니다. 돈이 부족해질 기미가 보이면 잠시 생활비를 줄이는 규칙 하나로 막을 수 있습니다.")
    ui.foot("고물가 스트레스는 시장 금리 고정(보수적). ① 공백기 준비금은 평상시 자녀 지원을 약 830만 줄여 추천에서 제외.")
