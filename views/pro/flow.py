import streamlit as st

from core import charts, ui

ui.head("3단계 · 재무상태 분석", "현금흐름 분석", "확률 사건이 없는 기본 경로 · 2026년 가치")
with st.container(border=True):
    ui.title("연도별 수입과 지출", "만 원/년")
    ui.show(charts.cashflow())
    ui.foot("위쪽 = 수입, 아래쪽 = 지출 · 검은 선 = 순현금흐름 · 음영 = 연금 공백기(2036~2039)")

c1, c2 = st.columns(2, gap="medium")
with c1, st.container(border=True):
    ui.title("은퇴 전후 순현금흐름", "2030~2042")
    ui.show(charts.net_bars())
    ui.foot("주황 = 적자(금융자산에서 인출) · 기본 경로")
with c2, st.container(border=True):
    ui.title("공백기 요약")
    ui.kpis([("4년 인출 (중앙값)", "1억 173만", "명목 · 2026년 가치 약 8,030만"), ("가장 큰 해", "2036년", "중앙값 4,598만 인출 (명목)")], cols=2)
    ui.timeline([("2036", "부부 모두 월급 없음, 배우자 연금 시작"), ("2037", "주택담보대출 상환 종료"), ("2039", "A씨 연금 시작 → 흑자 전환")])
    ui.easy("은퇴할 때 1억 원 정도를 안전한 곳에 따로 떼어 두면 공백기를 넘깁니다.")
