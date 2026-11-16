import streamlit as st

from core import charts, data as d, engine_link as el, ui

ui.head("상담", "우리 집이라면?", "조건을 바꾸면 엔진으로 다시 계산해 추천안(A씨 70·배우자 69세, 일시금, B00, 가드레일)과 비교합니다.")
S = {"B00": dict(name="B00 · 안정형", tag=("수학적 후보", "ok"), how="비상자금 6개월치(약 1,893만 원)는 예적금, 나머지는 모두 국내 채권. 주식 없음.",
                 who="원금이 크게 흔들리는 것이 불편하고, 공백기에 꺼내 쓸 돈이 확실히 있어야 하는 가구",
                 good="폭락이 와도 거의 흔들리지 않음 (연 변동성 약 2.8%). 22개 전략과 목표 달성률이 같아 위험이 가장 낮은 이 전략이 선정됨.",
                 bad="자산이 크게 불어나지는 않음. 100세 중앙값 5.2억 원."),
     "B40": dict(name="B40 · 성장형", tag=("성장 대안", "mu"), how="비상자금 6개월치는 예적금, 나머지의 40%는 주식·60%는 채권. 전체로 보면 주식 약 29%.",
                 who="일시적인 손실을 견딜 수 있고, 남는 자산을 더 키우고 싶은 가구",
                 good="평균적으로 자산이 더 많이 남음. 100세 중앙값 약 8.6억 원.",
                 bad="값이 크게 출렁임 (연 변동성 약 7.1%, B00의 2.5배). 은퇴 직후 폭락 시 나쁜 경우 자산이 4.05억 → 3.47억으로 줄고 실패 0.09% 발생. 목표 달성률은 B00과 통계적 차이 없음.")}

IDS = [x["id"] for x in d.D()["scatter"][d.BASE]]
IDS = ["B00", "B40"] + [i for i in IDS if i not in ("B00", "B40")]
def sname(k):
    if k in S:
        return S[k]["name"] + (" (주식 0%)" if k == "B00" else " (주식 약 29%)")
    return f"{k} · 비상자금 {3 if k[0] == 'A' else 6}개월, 나머지 중 주식 {k[1:]}%"

ss = st.session_state
c1, c2 = st.columns([3, 2], gap="medium")
with c1, st.container(border=True):
    ui.title("조건")
    with st.form("whatif_form", border=False):
        f = st.columns(3)
        a_age = f[0].selectbox("A씨 연금 개시", [70, 65, 60], index=1, format_func=lambda v: f"{v}세")
        s_age = f[1].selectbox("배우자 연금 개시", [69, 64, 59], index=1, format_func=lambda v: f"{v}세")
        method = f[2].selectbox("퇴직급여", ["lump_sum", "annuity"], format_func=d.METHODS.get)
        living = f[0].number_input("월 생활비 (만 원)", value=295.8, step=10.0, format="%.1f", min_value=150.0, max_value=600.0)
        child = f[1].selectbox("자녀 결혼·독립 지원 규모", list(el.CHILD_OPTS), format_func=el.CHILD_OPTS.get)
        guard = f[2].selectbox("생활비 가드레일", [False, True], format_func=lambda v: "켜기" if v else "끄기")
        strat = f[0].selectbox("투자전략", IDS, format_func=sname)
        market = f[1].selectbox("시장", list(d.MARKETS), format_func=d.MARKETS.get)
        run = st.form_submit_button("▶ 다시 계산", type="primary")
    ui.foot("연금 나이·퇴직급여·투자전략·시장만 바꾸면 본실험 1만 경로 결과를 바로 보여줍니다. "
            "생활비·자녀 지원·가드레일을 바꾸면 엔진을 1,000경로로 실시간 계산합니다(약 1분, 같은 조건을 다시 누르면 바로 표시).")

cond = dict(a=a_age, s=s_age, method=method, strategy=strat, living=round(living * 10_000), child=child, guard=guard)
if run or "whatif_last" not in ss:
    if el.needs_quick(cond):
        with st.spinner("엔진 계산 중… 1,000경로 × (바꾼 조건 + 추천안), 약 1분 걸립니다"):
            ss.whatif_last = (cond, market, *el.compute(cond, market))
    else:
        ss.whatif_last = (cond, market, *el.compute(cond, market))
lc, lm, mine, base, how = ss.whatif_last

with c2, st.container(border=True):
    ui.title("추천안과 비교", d.MARKETS[lm])
    ui.md(ui.badge(how, "ok" if "1만" in how else "mu"))
    ui.show(charts.pair_bars(["100세 중앙값", "나쁜 경우"], [mine["p50"], max(0, mine["cvar"])], [base["p50"], max(0, base["cvar"])],
                             "바꾼 조건", "추천안", h=260, ca="#FE9800", cb="#3182F6"), key="wcmp")

def delta(v, b, unit, good_up=True, nd=2):
    dv = v - b
    if abs(dv) < 10 ** -nd / 2:
        return "추천안과 같음"
    better = (dv > 0) == good_up
    return f"<span style='color:{'#03884F' if better else '#F04452'}'>추천안 대비 {dv:+.{nd}f}{unit}</span>"

ui.kpis([("100세 금융자산 (중앙값)", f"{mine['p50']:.2f}<small>억</small>", delta(mine["p50"], base["p50"], "억")),
         ("나쁜 경우 (하위 5% 평균)", f"{max(0, mine['cvar']):.2f}<small>억</small>", delta(mine["cvar"], base["cvar"], "억")),
         ("지금 생활 유지 실패", f"{mine['plan']:.2f}%", delta(mine["plan"], base["plan"], "%p", good_up=False)),
         ("기본 생활 부족", f"{mine['mini']:.2f}%", delta(mine["mini"], base["mini"], "%p", good_up=False)),
         ("자녀 지원 목표 미달", f"{mine['child']:.1f}%", delta(mine["child"], base["child"], "%p", good_up=False, nd=1))], cols=5)
ui.foot(f"조건: A씨 {lc['a']}세 · 배우자 {lc['s']}세 · {d.METHODS[lc['method']]} · 월 생활비 {lc['living'] / 10_000:.1f}만 · 자녀 지원 {el.CHILD_OPTS[lc['child']]} · "
        f"가드레일 {'켜기' if lc['guard'] else '끄기'} · {sname(lc['strategy'])} · 금액은 2026년 가치"
        + (" · 1,000경로라 하위 5% 값은 1만 경로보다 조금 흔들릴 수 있음" if "빠른" in how else ""))

with st.container(border=True):
    ui.title("투자전략 설명 · B00과 B40", "초기 금융자산 7,013만 원 기준")
    cols = st.columns(2, gap="medium")
    for col, k in zip(cols, ["B00", "B40"]):
        s = S[k]
        with col:
            ui.md(f"<div class='ct'><b>{s['name']}</b><span>{ui.badge(*s['tag'])}</span></div>")
            ui.show(charts.donut(k, 150), key=f"wd{k}")
            ui.table([None, None], [["어떻게 나누나", s["how"]], ["이런 분께", s["who"]], ["장점", s["good"]], ["주의할 점", s["bad"]]])
    p, q = d.strat("B00"), d.strat("B40")
    s1 = lambda k: d.stress(k, "S1")
    ui.table(["항목 (기준 시장)", "B00", "B40"], [
        ["예적금 / 채권 / 주식 (만 원)", " / ".join(f"{v:,}" for v in d.WON["B00"]), " / ".join(f"{v:,}" for v in d.WON["B40"])],
        ["연간 예상 변동성", f"{p['vol']:.2f}%", f"{q['vol']:.2f}%"], ["100세 금융자산 중앙값", f"{p['p50']:.2f}억", f"{q['p50']:.2f}억"],
        ["나쁜 경우 (하위 5% 평균)", f"{p['cvar']:.2f}억", f"{q['cvar']:.2f}억"], ["은퇴 직후 폭락 시 나쁜 경우", f"{s1('B00')['cvar']:.2f}억", f"{s1('B40')['cvar']:.2f}억"],
        ["지금 생활 유지 실패", f"{p['short']:.2f}%", f"{q['short']:.2f}%"]], num=(1, 2))
    ui.foot("이름 규칙: A/B = 비상자금 3/6개월, 숫자 = 비상자금을 뺀 나머지 중 주식 비율(%). 매년 초 리밸런싱. 세후 가정(예적금 2.81% · 채권 3.23% · 주식 8.30%).")
