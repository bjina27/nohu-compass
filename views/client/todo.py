import streamlit as st

from core import ai, ui

ui.head("마무리", "할 일 체크리스트", "지금부터 100세까지, 시기별로 챙길 일입니다. 끝낸 일은 체크해 보세요.")
TODO = [("지금", "비상자금 6개월치(약 1,900만 원)는 예금에, 나머지는 채권에 넣기"), ("매년 초", "목표 비율로 다시 맞추고, 생활비 규칙 점검하기"),
        ("2033년", "배우자 퇴직금 한 번에 받아 모아두기"), ("2035년", "A씨 퇴직금 받고, 약 1억 원은 '연금 기다리는 4년' 용으로 따로 두기"),
        ("2036년", "배우자 국민연금 신청 (69세)"), ("2039년", "A씨 국민연금 신청 (70세)"), ("빠듯할 때", "생활비를 잠시 월 216.6만 원으로 줄이기")]
with st.container(border=True):
    done = sum(bool(st.session_state.get(f"td{i}")) for i in range(len(TODO)))
    st.progress(done / len(TODO), text=f"{done} / {len(TODO)} 완료" + (" 🎉" if done == len(TODO) else ""))
    for i, (w, t) in enumerate(TODO):
        st.checkbox(f"**{w}** · {t}", key=f"td{i}")
ui.easy("생활비가 빠듯해지는 해가 오면 잠시 기본 생활비(월 216.6만 원)로 줄이고, 여유가 3년치 이상 생기면 원래대로 돌아가요. 이 규칙 하나로 물가 급등 같은 위기도 넘길 수 있어요.", "기억하세요")

ai.ask_button("c_todo")
