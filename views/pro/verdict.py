import streamlit as st

from core import charts, data as d, risk, ui

ui.head("4단계 · 적합성 검토", "적합성 평가 결과", "몬테카를로가 고른 수학적 후보를 그대로 확정할지, 상담이 필요한지 판정합니다.")
risk.init()
ss = st.session_state
ui.md("""<div class="steps"><div><em>STEP 1</em><b>세 가지 위험지표</b><span>수용성 · 감수능력 · 필요도</span></div>
<div><em>STEP 2</em><b>22개 전략 몬테카를로</b><span>같은 1만 경로로 비교</span></div>
<div><em>STEP 3</em><b>수학적 후보 B00</b><span>목표 동률 → 변동성 최저</span></div>
<div><em>STEP 4</em><b>적합성 검토</b><span>충돌 시 보류·상담</span></div></div>""")


def gauge(labels, idx):
    n = len(labels)
    return (f"<div class='gauge' style='grid-template-columns:repeat({n},1fr)'>" + "".join(f"<i class='{'on' if i == idx else ''}'></i>" for i in range(n)) +
            f"</div><div class='gl' style='grid-template-columns:repeat({n},1fr)'>" + "".join(f"<span>{l}</span>" for l in labels) + "</div>")


(va, ma), (vs, ms) = risk.use("a"), risk.use("s")
bands = [b["ko"] for b in d.D()["gl_bands"]]
SHORT = {"평균보다 낮음": "평균↓", "평균보다 높음": "평균↑"}
cap = risk.min_capacity()
c = st.columns(3, gap="medium")
with c[0], st.container(border=True):
    ui.title("위험수용성 (심리)")
    ui.md(f"<div class='big' style='font-size:26px;color:#191F28'>A씨 {va}점 · 배우자 {vs}점</div><div class='ft' style='margin:2px 0 0'>{d.band(va)} / {d.band(vs)}{' · 페르소나 모의응답' if ma or ms else ''}</div>" + gauge([SHORT.get(b, b) for b in bands], bands.index(d.band(va))))
with c[1], st.container(border=True):
    ui.title("위험감수능력 (재무)")
    ui.md(f"<div class='big' style='font-size:26px;color:#191F28'>{'확정 불가' if cap is None else ['낮음', '보통', '높음'][cap]}</div><div class='ft' style='margin:2px 0 0'>2026~2064 중 최저 · 외부 재원: {d.OUTSIDE[ss.outside]}</div>" + gauge(["낮음", "보통", "높음"], -1 if cap is None else cap))
with c[2], st.container(border=True):
    ui.title("위험필요도 (목표)")
    ui.md("<div class='big' style='font-size:26px;color:#191F28'>낮음</div><div class='ft' style='margin:2px 0 0'>요구수익률 0% · 필요 성장자산 0%</div>" + gauge(["낮음", "보통", "높음"], 0))

c1, c2 = st.columns([2, 1], gap="medium")
with c1, st.container(border=True):
    ui.title("후보 전략 적합성 검토", "기준 시장 · 비상자금 6개월(B)")
    pts = sorted([p for p in d.D()["scatter"][d.BASE] if p["id"][0] == "B"], key=lambda p: p["eq"])[:6]
    rows = []
    for p in pts:
        t, k, _ = risk.judge(p["eq"])
        rows.append([f"<b>{p['id']}</b>", f"{round(p['eq'] * 0.73)}%", f"{p['p50']:.2f}억", f"{p['cvar']:.2f}억", ui.badge(t, k)])
    ui.table(["전략", "주식 비중", "100세 중앙값", "나쁜 경우", "판정"], rows, num=(1, 2, 3), pick="<b>B00</b>")
    ui.foot("위험등급으로 주식 비중을 자동 변환하지 않습니다. 판정은 확정 / 조건부 / 보류만 냅니다.")
with c2, st.container(border=True):
    ui.title("결론")
    t, k, why = risk.judge(0)
    ui.md(ui.badge("판정 보류 · 외부 재원 확인" if ss.outside == "unknown" else "수학적 후보 B00 · 위험지표 충돌 없음 · 상담에서 확정", k))
    st.write(why)
    ui.easy("주식 없이 예적금과 채권만으로도 목표를 지킬 수 있고, 두 분이 감당할 수 있는 위험 범위 안에 있습니다. 최종 결정은 상담에서 함께 확인합니다.")
    st.page_link("views/pro/risk_input.py", label="← 입력 수정")

with st.container(border=True):
    ui.title("연도별 인출 비율과 감수능력", "C48 기본 경로, 계획 장부")
    ui.show(charts.liq_bars(ss.outside))
    ui.foot("공백기 2036~2039 인출 비율 16.4 → 5.6% · 주황 = 그해 CFA 낮음 · 외부 재원 설정에 따라 이 시기 등급이 달라짐")
