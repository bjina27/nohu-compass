import streamlit as st

from core import charts, data as d, ui

ui.head("4단계 · 재무설계안 수립 ②", "투자전략 비교", "22개 전략 몬테카를로 비교 → 수학적 후보")
market = st.selectbox("시장", list(d.MARKETS), format_func=d.MARKETS.get, key="inv_k")
c1, c2 = st.columns([2, 1], gap="medium")
with c1, st.container(border=True):
    ui.title("위험과 성과")
    ui.show(charts.scatter(market))
    ui.foot("가로 = 연간 예상 변동성, 세로 = 100세 금융자산 중앙값 · 빈 원 = 짝지은 검정 탈락")
with c2, st.container(border=True):
    ui.title("자산 구성")
    st.markdown("**B00 · 수학적 후보**")
    ui.show(charts.donut("B00", 160), key="d1")
    st.markdown("**B40 · 성장 대안**")
    ui.show(charts.donut("B40", 160), key="d2")
    ui.foot("비상자금 6개월 = 현금 27%, 나머지를 채권·주식으로")
ui.kpis([("선정 규칙", "<span style='font-size:18px'>목표 동률 → 변동성 최저</span>", "사전에 정한 규칙 · 그래서 B00", True),
         ("B40으로 바꾸면", "5.2 → 8.6억", "중앙값 증가 · 폭락·하향 시장에 약함"),
         ("하향 시장 검정 탈락", "4개", "주식 90~100% · 실패 0.14~0.21%")], cols=3)
