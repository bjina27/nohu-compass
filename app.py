"""노후나침반 — A씨 가구 노후 재무설계 (AFPK 공모전 팀_B안)

실행: streamlit run app.py
설계사 화면(재무설계 6단계 순서)과 고객 화면(일반인용)을 오른쪽 위 버튼으로 전환한다.
"""
import streamlit as st

from core import ui, risk

st.set_page_config(page_title="노후나침반", page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
ui.inject()
risk.init()
st.logo("assets/logo.svg", size="large")

# (파일, 제목, 아이콘, 주소). 두 화면의 페이지를 모두 등록하고, 지금 화면이 아닌 쪽은 메뉴에서만 숨긴다
# → /c-life 같은 주소로 바로 들어와도 열리고, 그 주소에 맞춰 화면 모드가 바뀐다.
PRO = {
    "요약": [("views/pro/home.py", "종합 요약", ":material/home:", "home")],
    "1·2단계 관계·자료 수집": [("views/pro/family.py", "가계 정보", ":material/group:", "family"),
                          ("views/pro/risk_input.py", "위험평가 입력", ":material/assignment:", "risk")],
    "3단계 분석": [("views/pro/flow.py", "현금흐름 분석", ":material/bar_chart:", "flow")],
    "4단계 설계안": [("views/pro/pension.py", "연금 개시 시기", ":material/payments:", "pension"),
                 ("views/pro/invest.py", "투자전략 비교", ":material/show_chart:", "invest"),
                 ("views/pro/verdict.py", "적합성 검토", ":material/verified:", "verdict")],
    "5·6단계 실행·점검": [("views/pro/plan.py", "실행 계획", ":material/checklist:", "plan"),
                     ("views/pro/stress.py", "위기 테스트", ":material/shield:", "stress"),
                     ("views/pro/sense.py", "민감도 분석", ":material/tune:", "sense")],
    "상담": [("views/pro/whatif.py", "우리 집이라면?", ":material/calculate:", "whatif"),
           ("views/pro/advisor.py", "AI 상담", ":material/forum:", "advisor"),
           ("views/pro/method.py", "방법론·한계", ":material/menu_book:", "method")],
}
CLIENT = {
    "시작": [("views/client/home.py", "한눈에 보기", ":material/home:", "c-home")],
    "우리 집": [("views/client/money.py", "돈의 흐름", ":material/bar_chart:", "c-money"),
              ("views/client/life.py", "44년 미리 보기", ":material/play_circle:", "c-life")],
    "나를 알기": [("views/client/risk.py", "투자 성향 알아보기", ":material/psychology:", "c-risk")],
    "결정할 것": [("views/client/pension.py", "연금 언제 받을까", ":material/payments:", "c-pension"),
              ("views/client/invest.py", "돈 어떻게 굴릴까", ":material/savings:", "c-invest"),
              ("views/client/whatif.py", "만약에?", ":material/shield:", "c-whatif")],
    "마무리": [("views/client/todo.py", "할 일 체크리스트", ":material/task_alt:", "c-todo")],
}
MODES = ("설계사 화면", "고객 화면")
ss = st.session_state
ss.setdefault("mode", MODES[0])


def build(spec, visible):
    return {sec: [st.Page(f, title=t, icon=i, url_path=u, default=(u == "home"), visibility="visible" if visible else "hidden")
                  for f, t, i, u in rows] for sec, rows in spec.items()}


pro, client = build(PRO, ss.mode == MODES[0]), build(CLIENT, ss.mode == MODES[1])
shown, hidden = (pro, client) if ss.mode == MODES[0] else (client, pro)
menu = {k: list(v) for k, v in shown.items()}
menu[list(menu)[-1]] += [pg for v in hidden.values() for pg in v]
nav = st.navigation(menu)

# 버튼으로 화면을 바꿨으면 그 화면의 첫 페이지로 이동 (주소 검사보다 먼저)
if ss.pop("_jump", False):
    st.switch_page((pro["요약"] if ss.mode == MODES[0] else client["시작"])[0])

# 주소가 다른 화면의 페이지면 모드를 맞춘다 (주소로 바로 들어온 경우)
want = MODES[1] if (nav.url_path or "").startswith("c-") else MODES[0]
if want != ss.mode:
    ss.mode = want
    st.rerun()


def _switch():
    if ss._mode_sel and ss._mode_sel != ss.mode:
        ss.mode = ss._mode_sel
        ss._jump = True


ss._mode_sel = ss.mode
l, r = st.columns([3, 2], vertical_alignment="center")
l.markdown('<span style="font-size:13px;color:#6B7684">👤 A씨 가구 (페르소나) · 웹 시안, 숫자는 실제 1만 경로 결과</span>', unsafe_allow_html=True)
with r:
    st.segmented_control("화면", list(MODES), key="_mode_sel", on_change=_switch, label_visibility="collapsed", width="content")
    st.markdown("<style>.st-key-_mode_sel{display:flex;justify-content:flex-end}</style>", unsafe_allow_html=True)

nav.run()
