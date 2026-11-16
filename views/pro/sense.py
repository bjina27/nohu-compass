import streamlit as st

from core import charts, ui

ui.head("6단계 · 점검 ②", "민감도 분석", "가정을 하나씩 바꿔 결과가 얼마나 흔들리는지 (토네이도)")
with st.container(border=True):
    ui.title("나쁜 경우 남는 자산의 변화", "기준 3.30억 대비, 억 원")
    ui.show(charts.tornado())
    ui.foot("파랑 = 낮은 값, 주황 = 높은 값 · 마우스를 올리면 범위 근거")
ui.kpis([("1위 생활비", "±1.7억", "월 30만 원 차이"), ("2위 국민연금 급여", "±1.55억", "제도 변화 가능성"), ("물가 (금리 동반)", "±0.2억", "피셔 효과로 상쇄")], cols=3)
ui.info("재취업은 극단값 범위라 참고용. 상호작용 미반영, 임금 막대는 퇴직금 비례 근사, 퇴직연령 막대 제외.")
