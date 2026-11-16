import streamlit as st

from core import ai, ui

dots = "".join(f'<i style="animation-delay:{i * 14}ms"></i>' for i in range(100))
ui.md(f"""<section class="hero"><div>
<span class="chip">A씨 가족 노후 진단 결과</span>
<h1>결론부터 말하면,<br>괜찮습니다.</h1>
<p>앞으로 44년(100세까지)의 미래를 컴퓨터로 <b>1만 번</b> 그려 봤어요. 주가가 떨어지고, 물가가 오르고, 가족에게 일이 생기는 경우까지 모두 넣었습니다.</p>
<p class="say"><b>1만 번 모두에서 기본 생활비가 바닥나지 않았어요.</b></p></div>
<div><div class="dots" aria-label="1만 개 미래 중 기본 생활이 지켜진 비율 100%">{dots}</div>
<p style="font-size:13px;color:#8B95A1;margin-top:10px">점 하나 = 미래 100개 · 초록 = 기본 생활이 지켜진 미래</p></div></section>""")

ui.kpis([("100세에 남는 돈 · 보통의 경우", f"{ui.count(5.2, 1)}<small>억 원</small>", "오늘 돈 가치로 계산", True),
         ("운이 아주 나쁜 경우에도", f"{ui.count(3.3, 1)}<small>억 원</small>", "나쁜 미래 5%의 평균", True),
         ("은퇴 직후 4년간 꺼내 쓸 돈", f"{ui.count(8000)}<small>만 원</small>", "월급도 연금도 없는 시기 (2036~2039)", True)], cols=3)
ui.count_js()

st.markdown("### 그러려면 세 가지만 지키세요")
c = st.columns(3, gap="medium")
for col, (n, t, body, page, lbl) in zip(c, [
        (1, "국민연금은 늦게 받기", "A씨 70세, 배우자 69세에 받으면 매달 받는 연금이 제때보다 36% 커져요.", "views/client/pension.py", "왜 그런지 보기 →"),
        (2, "은퇴할 때 1억은 따로", "월급도 연금도 없는 4년을 버틸 돈이에요. 퇴직금으로 마련해요.", "views/client/life.py", "44년 미리 보기 →"),
        (3, "투자는 안정형으로", "예금과 채권만으로도 충분해요. 주식으로 모험할 필요가 없어요.", "views/client/invest.py", "두 방법 비교 →")]):
    with col:
        ui.md(f'<div class="key"><span class="n">{n}</span><div><h3>{t}</h3><p>{body}</p></div></div>')
        st.page_link(page, label=lbl)

ai.ask_button("c_home")
