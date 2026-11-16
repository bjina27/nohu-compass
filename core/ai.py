"""AI 상담. .streamlit/secrets.toml 에 OPENAI_API_KEY 가 있으면 GPT로 답하고, 없으면 예시 답변만 보여준다.

키 파일은 절대 저장소·zip에 넣지 않는다(.gitignore 처리).
"""
import streamlit as st

from core import data as d

SYS_CLIENT = """너는 '노후나침반' 고객 화면의 설명 도우미다. 고객은 금융 비전문가인 50대 후반 A씨 부부다.
규칙:
1) 아래 [계산 결과]에 있는 숫자만 근거로, 쉬운 한국어 존댓말 3~5문장으로 답한다. 없는 숫자는 만들지 않는다.
2) 특정 금융상품 추천, 매수·매도 권유, 수익 보장 같은 확정적 표현을 하지 않는다.
3) 결정이 필요한 질문(무엇을 고를지, 바꿀지)은 이유를 설명한 뒤 '최종 결정은 설계사 상담에서 함께 정해요'로 안내한다.
4) 전문용어는 풀어서 쓴다(예: CVaR → 운이 아주 나쁜 경우, 2026년 가치 → 오늘 돈 가치)."""

SYS_PRO = """너는 '노후나침반' 설계사 화면의 분석 보조다. 사용자는 재무설계사다.
규칙: [계산 결과]의 수치를 근거로 간결하게 답하고, 어떤 결과(조합·전략·시장·장부)를 근거로 했는지 마지막 줄에 '근거:'로 적는다.
결과에 없는 조건 변경은 추정하지 말고 '엔진 재계산 필요'라고 말한다. 위험등급을 주식 비중으로 자동 변환하지 않는다."""


def _key():
    try:
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


def enabled():
    return bool(_key())


def ask(question, mode="client", page_context=""):
    key = _key()
    if not key:
        return None
    from openai import OpenAI
    try:
        model = st.secrets.get("OPENAI_MODEL", "gpt-4o-mini")
    except Exception:
        model = "gpt-4o-mini"
    sys = (SYS_CLIENT if mode == "client" else SYS_PRO) + "\n\n[계산 결과]\n" + d.FACTS + ("\n[지금 보는 화면]\n" + page_context if page_context else "")
    r = OpenAI(api_key=key).chat.completions.create(
        model=model, temperature=0.3,
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": question}])
    return r.choices[0].message.content


# 고객 화면 페이지별 추천 질문과 예시 답변(키가 없을 때 사용)
ASK = {
    "c_home": [("1만 번 그려봤다는 게 무슨 뜻이에요?", "앞으로 주가·물가·가족 일이 어떻게 될지는 아무도 몰라요. 그래서 일어날 수 있는 미래를 컴퓨터로 1만 가지 만들고, 그 모든 경우에 돈이 버티는지 확인했어요."),
               ("'운이 아주 나쁜 경우'는 얼마나 나쁜 거예요?", "1만 개 미래를 100세에 남는 돈 순서로 줄 세웠을 때 가장 나쁜 500개(5%)의 평균이에요. 그 경우에도 오늘 가치로 약 3.3억 원이 남아요.")],
    "c_money": [("왜 은퇴 직후 4년이 제일 빠듯해요?", "2035년 A씨 은퇴로 월급이 끊기지만, A씨 연금은 70세(2039년)에 시작해요. 그 4년은 배우자 연금만으로는 생활비가 모자라 모아둔 돈을 꺼내 써요."),
                ("1억은 어디에 둬야 해요?", "예금이나 채권처럼 원금이 잘 흔들리지 않는 곳이 좋아요. 구체적인 상품은 설계사 상담에서 정해요.")],
    "c_life": [("모아둔 돈이 왜 줄었다가 다시 늘어요?", "2036~2039년에는 월급도 A씨 연금도 없어서 모아둔 돈을 꺼내 써요. 2039년 A씨 연금이 시작되면 다시 돈이 남아 조금씩 늘어나요."),
               ("아들 결혼 비용은 왜 안 나와요?", "이 화면은 정해진 일만 보여줘요. 결혼은 생길 수도 있는 일이라 '만약에?'에서 따로 계산했어요. 결혼·독립 비용이 가장 나쁜 때 몰려도 생활은 지켜져요.")],
    "c_risk": [("정답이 있는 질문이에요?", "아니요. 두 분이 돈의 손실을 얼마나 편하게 받아들이는지 알아보는 질문이라, 솔직하게 답하시면 돼요."),
               ("점수가 낮으면 불리해요?", "아니요. 점수는 투자 방법을 고를 때 참고만 해요. 점수로 주식 비율을 자동으로 정하지 않아요.")],
    "c_pension": [("일찍 받으면 더 오래 받으니까 이득 아니에요?", "받는 기간은 5년 길지만 매달 30% 적게 받아요. A씨 가족은 100세까지 보면 늦게 받을 때 남는 돈이 보통 5.2억 원, 일찍 받으면 0.35억 원이에요. 다만 두 분이 오래 사신다는 가정이에요."),
                  ("연금을 기다리는 동안은 어떻게 살아요?", "퇴직금으로 약 1억 원을 따로 떼어 두고, 4년 동안 그 돈으로 모자란 생활비를 메워요.")],
    "c_invest": [("주식이 없으면 물가를 못 따라가지 않아요?", "이번 계산은 물가를 반영한 오늘 가치로 했어요. 예금·채권 수익만으로도 100세까지 돈이 바닥나지 않았어요. 꼭 필요한 수익률이 0%라서 주식으로 위험을 질 필요가 없어요."),
                 ("성장형을 고르면 안 되나요?", "고를 수 있어요. 목표 달성은 둘 다 같고, 성장형은 남는 돈이 더 많지만 값이 더 출렁여요. 손실을 어디까지 견딜 수 있는지 설계사와 확인한 뒤 정해요.")],
    "c_whatif": [("물가가 오르면 왜 위험해요?", "생활비는 바로 오르는데 예금·채권 이자는 바로 따라오지 않아요. 은퇴 직후 돈을 꺼내 쓰는 시기와 겹치면 빠듯해져서 '빠듯하면 잠시 아껴 쓰기' 규칙을 둬요."),
                 ("아껴 쓰기 규칙은 얼마나 자주 써요?", "물가 급등이 온 미래 중에서도 100번에 1번 정도, 평균 2년쯤만 써요. 평소에는 거의 쓸 일이 없어요.")],
    "c_todo": [("언제 다시 상담받아야 해요?", "매년 초, 그리고 은퇴(2033·2035년)와 국민연금 신청(2036·2039년) 전에는 꼭 설계사와 점검하세요."),
               ("계획대로 안 되면 어떡해요?", "생활비, 연금, 가족 상황이 바뀌면 다시 계산해서 계획을 고쳐요. 이 계획은 한 번 정하고 끝나는 게 아니에요.")],
}


def ask_button(page_key, context=""):
    """고객 화면 오른쪽 아래 떠 있는 '물어보기'."""
    hist = st.session_state.setdefault(f"ask_{page_key}", [])
    with st.popover("💬 물어보기", key="askpop"):
        st.markdown("**AI에게 물어보기**")
        st.caption("계산 결과를 쉬운 말로 설명해 드려요. 상품 추천이나 최종 결정은 설계사 상담에서 해요." + ("" if enabled() else " (예시 답변)"))
        for q, a in hist:
            st.chat_message("user").write(q)
            st.chat_message("assistant").write(a)
        asked = {q for q, _ in hist}
        for i, (q, a) in enumerate(ASK.get(page_key, [])):
            if q not in asked and st.button(q, key=f"sug_{page_key}_{i}", width="stretch"):
                hist.append((q, (ask(q, "client", context) if enabled() else None) or a))
                st.rerun()
        with st.form(f"askf_{page_key}", clear_on_submit=True, border=False):
            q = st.text_input("질문", placeholder="궁금한 점을 입력하세요", label_visibility="collapsed")
            if st.form_submit_button("보내기", type="primary") and q.strip():
                a = ask(q, "client", context) if enabled() else "지금은 예시 화면이에요. AI 키를 연결하면 이 질문에 계산 결과를 근거로 답해 드려요."
                hist.append((q, a))
                st.rerun()
