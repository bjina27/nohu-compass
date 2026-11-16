import streamlit as st

from core import charts, data as d, ui

ui.head("4단계 · 재무설계안 수립 ①", "국민연금 개시 시기", "9가지 조합을 같은 1만 개 미래에서 비교 (투자 B00 고정)")
a, b, _ = st.columns([1, 1, 2])
method = a.selectbox("퇴직급여 방식", list(d.METHODS), format_func=d.METHODS.get, key="pen_m")
market = b.selectbox("시장", list(d.MARKETS), format_func=d.MARKETS.get, key="pen_k")

c1, c2 = st.columns(2, gap="medium")
with c1, st.container(border=True):
    ui.title("조합별 나쁜 경우 남는 자산", "억 원 · 굵은 테두리 = 추천")
    ui.show(charts.heatmap(market, method))
    ui.foot("큰 숫자 = 하위 5% 평균 남는 자산 · 작은 숫자 = 지금 생활 유지 실패 확률")
with c2, st.container(border=True):
    ui.title("일찍 vs 제때 vs 늦게", "100세 금융자산, 억 원")
    ui.show(charts.claim_bars(market, method))
ui.easy("두 분 모두 연금을 늦게 받을수록 노후가 넉넉해집니다. 특히 배우자가 59세에 일찍 받으면 크게 나빠집니다.")
ui.info("조정률(엔진 동일, 세전): 조기 월 0.5% 감액(5년 −30%) · 연기 월 0.6% 가산(5년 +36%). 한계: 부부 사망 미모델링 → 연기수령 이점이 실제보다 클 수 있음(보고서에 명시).")
