import streamlit as st

from core import charts, ui

ui.head("요약", "A씨 부부 노후 재무설계 요약", "양가 어머니와 아들을 도우면서 100세(2069년)까지 괜찮은지, 1만 개의 미래로 확인했습니다.")
ui.kpis([("기본 생활이 지켜진 미래", "100%", "최소생활비 월 216.6만 + 양가 어머니 지원", True),
         ("지금 생활이 유지된 미래", "99.99%↑", "월 295.8만 · 생활비 가드레일 포함", True),
         ("100세 금융자산 (중앙값)", "5.20<small>억</small>", "나쁜 경우 3.30억 · 2026년 가치", True),
         ("연금 공백기 인출 (4년)", "약 1<small>억</small>", "2036~2039 · 2026년 가치 약 8천만", True)])
ui.easy("국민연금을 늦게 받고 은퇴 직후 4년만 잘 버티면, 어떤 미래에서도 기본 생활은 무너지지 않습니다.")

c1, c2 = st.columns([2, 1], gap="medium")
with c1, st.container(border=True):
    ui.title("100세까지 금융자산 범위", "억 원 · 2026년 가치")
    ui.show(charts.fan())
    ui.foot("진한 띠 25~75% · 옅은 띠 5~95% · 음영 = 연금 공백기")
with c2, st.container(border=True):
    ui.title("추천 재무설계안")
    ui.timeline([("2033", "배우자 은퇴 · 퇴직급여 일시금"), ("2035", "A씨 은퇴 · 퇴직급여 일시금"), ("2036", "배우자 국민연금 (69세)"),
                 ("2036~39", "공백기: 금융자산에서 약 1억 인출"), ("2039", "A씨 국민연금 (70세)")])
    ui.chips(["투자 B00 · 주식 0%", "비상자금 6개월", "생활비 가드레일"])
    ui.show(charts.donut("B00", 170))

c = st.columns(3, gap="medium")
for col, (t, body, page) in zip(c, [
        ("🛡️ 위기 테스트", "폭락·고물가·가족 사건을 겹쳐도 기본 생활 부족 0~0.05%. 고물가 약점은 가드레일로 0%.", "views/pro/stress.py"),
        ("📊 가장 큰 변수", "생활비(월 ±30만 → 약 ±1.7억)와 국민연금 급여가 투자 수익률보다 큽니다.", "views/pro/sense.py"),
        ("🎯 위험 성향", "필요도 낮음 · 감수능력 보통 · 수용성 보통(모의). B00과 충돌 없음, 상담에서 확정.", "views/pro/verdict.py")]):
    with col, st.container(border=True):
        ui.title(t)
        st.write(body)
        st.page_link(page, label="자세히 보기 →")
