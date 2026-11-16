import streamlit as st

from core import charts, ui

ui.head("5단계 · 재무설계안 실행", "실행 계획", "할 일과 점검 시점")
c1, c2 = st.columns([2, 1], gap="medium")
with c1, st.container(border=True):
    ui.title("100세까지 금융자산 범위", "억 원 · 2026년 가치")
    ui.show(charts.fan(420))
    ui.foot("진한 띠 25~75% · 옅은 띠 5~95%")
with c2, st.container(border=True):
    ui.title("할 일")
    ui.timeline([("지금", "비상자금 6개월치(약 1,893만) 예적금, 나머지 채권"), ("매년 초", "목표 비중으로 리밸런싱, 가드레일 점검"),
                 ("2033", "배우자 퇴직급여 일시금 수령"), ("2035", "A씨 퇴직급여 일시금, 공백기 자금 약 1억 확보"),
                 ("2036", "배우자 국민연금 신청 (69세)"), ("2039", "A씨 국민연금 신청 (70세)")])
    ui.info("<b>생활비 가드레일</b> — 연초 금융자산이 올해+내년 필수 순지출보다 적으면 생활비를 월 216.6만으로 줄이고, 3년치 이상 회복되면 원래대로.")
