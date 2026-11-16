import streamlit as st

from core import charts, data as d, risk, ui

ui.head("1·2단계 · 자료 수집", "위험평가 입력", "세 가지 위험지표를 각각 평가합니다. 이 결과만으로 투자 비중을 자동 변경하지 않습니다.")
risk.init()
ss = st.session_state
n = d.D()["need"]

# 카드 높이가 달라 생기는 빈 공간을 없애려고 열마다 카드를 위아래로 쌓는다
left, right = st.columns(2, gap="medium")

with left:
    with st.container(border=True):
        ui.title("1. 위험수용성 · G&L 13문항")
        risk.survey("p")

    with st.container(border=True):
        ui.title("3. 위험필요도 · Risk Need")
        goal = st.segmented_control("목표 지출 범위", ["계획지출 전체", "최소생활비"], default="계획지출 전체", key="goal")
        ui.kpis([("현금(예적금)", f"{n['cash']:.2f}%", "세후"), ("채권", f"{n['bond']:.2f}%", "세후"), ("주식", f"{n['eq']:.2f}%", "세후")], cols=3, fixed=True)
        ui.show(charts.need_bars(170))
        ui.foot(f"{goal or '계획지출 전체'} 기준 요구수익률 {n['req'] * 100:.2f}% → 필요 성장자산 {n['growth'] * 100:.0f}% → {n['rating']}. "
                "연도별 현금흐름은 엔진(C48)과 자동 연동, 시장 가정은 몬테카를로와 동일(세후).")

with right:
    with st.container(border=True):
        ui.title("2. 위험감수능력 · CFA + ALM")
        ui.table([None, None], [["투자기간", "현금흐름 엔진(C48)에서 연도별 자동 계산 (2069년까지)"],
                                ["유동성 수요", "연간 인출 비율 = 순인출 ÷ 연초 금융자산"]])
        keys = list(d.OUTSIDE)
        ss.outside = st.selectbox("비상시 외부 소득·자산 충분성", keys, index=keys.index(ss.outside), format_func=d.OUTSIDE.get)
        st.markdown("**ALM 필수지출 포함 항목**")
        a, b = st.columns(2)
        for i, (t, v) in enumerate([("최소생활비 216.6만", True), ("주택담보대출 원리금", True), ("건강·의료비", True),
                                    ("양가 어머니 지원", True), ("아들 지원 (계획지출로 분리)", False)]):
            (a if i % 2 == 0 else b).checkbox(t, value=v, disabled=True, key=f"alm{i}")
        ui.title("연도별 CFA 판정", "칸에 마우스를 올리면 인출 비율·바닥·완충액")
        ui.show(charts.cfa_strip(ss.outside), key="strip")
        ui.md("<div class='chips'>"
              "<span class='chip' style='background:#FE9800;color:#fff'>낮음</span>"
              "<span class='chip' style='background:#3182F6;color:#fff'>보통</span>"
              "<span class='chip' style='background:#1B64DA;color:#fff'>높음</span>"
              "<span class='chip' style='background:#D1D6DB;color:#4E5968'>확정 불가</span></div>")
        ui.foot("외부 재원을 '없음'으로 바꾸면 공백기(2036–2039)가 낮음으로 바뀝니다. 2065–2069는 남은 기간이 5년 이하라 규칙상 낮음.")

    with st.container(border=True):
        ui.title("입력 상태 및 실행")
        na, _ = risk.score("a")
        ns, _ = risk.score("s")
        done = na == 13 and ns == 13
        rows = [(True, "가계 재무정보 연동 완료 (C48 현금흐름)"),
                (done, f"G&L 설문 A씨 {na}/13 · 배우자 {ns}/13" + ("" if done else " (미완료 → 모의응답)")),
                (ss.outside != "unknown", "외부 재원 판단 필요" if ss.outside == "unknown" else f"외부 재원: {d.OUTSIDE[ss.outside]}"),
                (True, "시장가정 연결됨 (세후, 몬테카를로와 동일)")]
        ui.md("<div class='lights'>" + "".join(f"<div><span class='lamp {'g' if ok else 'y'}'></span>{t}</div>" for ok, t in rows) + "</div>")
        if st.button("▶ 위험평가 실행 → 적합성 검토", type="primary", width="stretch"):
            st.switch_page("views/pro/verdict.py")
        ui.foot("실제 추천전략은 위험평가와 별도로 몬테카를로 전략비교(4단계)에서 산출됩니다.")
