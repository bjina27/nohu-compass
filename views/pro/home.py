import streamlit as st

from core import charts, data as d, engine_link as el, ui

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
    ui.foot("진한 띠 25~75% · 옅은 띠 5~95% · 주황 점선 사이 = 연금 공백기")
with c2, st.container(border=True):
    ui.title("추천 재무설계안")
    ui.timeline([("2033", "배우자 은퇴 · 퇴직급여 일시금"), ("2035", "A씨 은퇴 · 퇴직급여 일시금"), ("2036", "배우자 국민연금 (69세)"),
                 ("2036~39", "공백기: 금융자산에서 약 1억 인출"), ("2039", "A씨 국민연금 (70세)")])
    ui.chips(["투자 B00 · 주식 0%", "비상자금 6개월", "생활비 가드레일"])
    ui.show(charts.donut("B00", 170))
    ui.info("<b>B00 = 안정형 포트폴리오</b> — 비상자금 6개월치(약 1,892만 원)는 예적금, 나머지는 모두 채권, 주식 0%. "
            "<span style='color:#8B95A1'>이름 규칙: B = 비상자금 6개월(A = 3개월), 00 = 나머지 중 주식 비율 0%</span>")

# ---- 왜 이 안인가: 연금 조합 Top5 / 투자전략 후보 5
TOP = [("C48", 70, 69, "lump_sum"), ("C33", 65, 69, "annuity"), ("C30", 65, 69, "lump_sum"), ("C42", 70, 64, "lump_sum"), ("C15", 60, 69, "annuity")]
with st.container(border=True):
    ui.title("왜 이 안인가", "기준 시장 · 1만 경로")
    t1, t2 = st.tabs(["연금 수령 조합 Top 5", "투자전략 후보 5"])
    with t1:
        rows = []
        for i, (cid, a, s_, m) in enumerate(TOP, 1):
            v = el.lookup(a, s_, m, "B00", d.BASE)
            rows.append([f"<b>{i}위</b>", f"A씨 {a}세 · 배우자 {s_}세", d.METHODS[m].replace("퇴직급여 ", ""), f"{v['p50']:.2f}억", f"{v['cvar']:.2f}억",
                         f"{v['child']:.1f}%", ui.badge("추천", "ok") if i == 1 else ui.badge("1위보다 확실히 나쁨", "mu")])
        ui.table(["순위", "국민연금 개시", "퇴직급여", "100세 중앙값", "나쁜 경우", "자녀 지원 미달", "1위와 비교"], rows, num=(3, 4, 5), pick="<b>1위</b>")
        ui.foot("순위 규칙: 현행 생활비 조합 중 기본 생활 부족 → 지금 생활 부족(0.1%p 이내는 동률) → 나쁜 경우 자산 → 중앙값 순, 22개 투자전략 평균. "
                "1위 C48은 22개 전략 모두에서 1위였고, 새 seed로 다시 돌려도 순위가 같았습니다. 표의 금액은 B00 기준.")
        st.page_link("views/pro/pension.py", label="연금 개시 시기 9가지 조합 전체 보기 →")
    with t2:
        pts = sorted([p for p in d.D()["scatter"][d.BASE] if p["pass"]], key=lambda p: p["vol"])[:5]
        rows = []
        for p in pts:
            em = 6 if p["id"][0] == "B" else 3
            total_eq = round(p["eq"] * (0.73 if em == 6 else 0.865))
            rows.append([f"<b>{p['id']}</b>", f"비상자금 {em}개월 · 주식 {total_eq}%", f"{p['vol']:.2f}%", f"{p['p50']:.2f}억", f"{p['cvar']:.2f}억",
                         "✓" if p["short"] < 0.05 else f"{p['short']:.2f}%", ui.badge("선택", "ok") if p["id"] == "B00" else ""])
        ui.table(["전략", "구성", "변동성", "100세 중앙값", "나쁜 경우", "목표 달성", ""], rows, num=(2, 3, 4), pick="<b>B00</b>")
        ui.foot("22개 전략 모두 목표(지금 생활 유지) 달성률이 통계적으로 같았습니다(짝지은 검정). 그래서 미리 정한 규칙대로 "
                "<b>위험(변동성)이 가장 낮은 B00</b>을 골랐습니다. 주식이 늘면 남는 돈은 커지지만 값이 더 출렁입니다. 변동성 낮은 순 5개.")
        st.page_link("views/pro/invest.py", label="22개 투자전략 전체 보기 →")

c = st.columns(3, gap="medium")
for col, (t, body, page) in zip(c, [
        ("🛡️ 위기 테스트", "폭락·고물가·가족 사건을 겹쳐도 기본 생활 부족 0~0.05%. 고물가 약점은 가드레일로 0%.", "views/pro/stress.py"),
        ("📊 가장 큰 변수", "생활비(월 ±30만 → 약 ±1.7억)와 국민연금 급여가 투자 수익률보다 큽니다.", "views/pro/sense.py"),
        ("🎯 위험 성향", "필요도 낮음 · 감수능력 보통 · 수용성 보통(모의). B00과 충돌 없음, 상담에서 확정.", "views/pro/verdict.py")]):
    with col, st.container(border=True):
        ui.title(t)
        st.write(body)
        st.page_link(page, label="자세히 보기 →")
