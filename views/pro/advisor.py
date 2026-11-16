import streamlit as st

from core import ai, ui

ui.head("상담", "AI 상담", "질문을 이해해 계산 결과를 근거로 답합니다" + ("" if ai.enabled() else " · 지금은 예시 화면 (secrets.toml에 OPENAI_API_KEY를 넣으면 GPT 연결)"))
ss = st.session_state
ss.setdefault("pro_chat", [
    ("user", "퇴직하고 연금 나올 때까지 버틸 수 있을까요?"),
    ("assistant", "네. 2036~2039년 4년 동안 금융자산에서 약 1억 원(2026년 가치 약 8천만 원)을 꺼내 쓰게 되지만, 은퇴 시점 금융자산 중앙값 약 3.4억 원으로 충분합니다. "
                  "다만 그 직전에 자녀 지원이 크게 겹치고 물가까지 오르면 위험해질 수 있어, 생활비 가드레일을 함께 두길 권합니다.\n\n근거: C48 + B00, 계획 장부, 1만 경로 중앙값"),
    ("user", "연금을 그냥 65세, 64세에 받으면요?"),
    ("assistant", "100세 금융자산 중앙값이 5.20억 원에서 3.07억 원으로, 나쁜 경우가 3.30억 원에서 1.15억 원으로 줄어듭니다. 지금 생활을 못 지키는 확률은 0.01%로 여전히 낮지만 여유가 크게 줄어요.\n\n근거: C24 + B00 vs C48 + B00, 기준 시장, 1만 경로")])
with st.container(border=True, height=520):
    for role, msg in ss.pro_chat:
        st.chat_message(role).write(msg)
q = st.chat_input("질문을 입력하세요 (예: B40으로 바꾸면 폭락 때 얼마나 줄어요?)")
if q:
    a = ai.ask(q, "pro") if ai.enabled() else "예시 화면입니다. OPENAI_API_KEY를 연결하면 계산 결과를 근거로 답합니다."
    ss.pro_chat += [("user", q), ("assistant", a)]
    st.rerun()
