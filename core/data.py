"""시뮬레이션 결과(1만 경로) 읽기와 공통 상수.

data/results.json 은 afpk_simulation 결과에서 뽑은 화면용 요약이다.
(cashflow=확률 사건 없는 기본 경로, fan=C48+B00 금융자산 분위, heat=연금 9조합,
 scatter=22전략, stress/guard/tornado=점검, gl_*/cfa/need=위험지표 모듈)
"""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE, DOWN = "base_846_aftertax", "down_600_aftertax"
MARKETS = {BASE: "기준 시장 (주식 8.46%)", DOWN: "하향 시장 (주식 6.00%)"}
METHODS = {"lump_sum": "퇴직급여 일시금", "annuity": "퇴직급여 IRP 연금"}
GAP = (2036, 2039)
MOCK = {"a": 23, "s": 26}                      # G&L 페르소나 모의응답
WEIGHTS = {"B00": [27, 73, 0], "B40": [27, 43.8, 29.2]}  # 예적금/채권/주식 %
WON = {"B00": [1893, 5120, 0], "B40": [1893, 3072, 2048]}  # 초기 7,013만 원 배분
OUTSIDE = {"none": "없음", "some": "있으나 불충분 (페르소나 가정)", "sufficient": "충분함", "unknown": "미확인"}
STRESS_NAMES = {"S0": "충격 없음", "S1": "은퇴 직후 폭락", "S2": "5년 고물가", "S3b": "가족 사건 최악", "S4b": "가족 사건 + 폭락"}
GUARD_NAMES = {"none": "없음", "bridge": "① 공백기 준비금", "living": "② 생활비 가드레일", "both": "①+②"}
PEN = {"early": (60, 59, "일찍", 70), "normal": (65, 64, "제때", 100), "late": (70, 69, "늦게", 136)}


@lru_cache(maxsize=1)
def D():
    return json.loads((ROOT / "data" / "results.json").read_text(encoding="utf-8"))


def years():
    return D()["fan"]["years"]


def cf(year):
    return next(r for r in D()["cashflow"] if r["year"] == year)


def heat(market=BASE, method="lump_sum"):
    return D()["heat"][f"{market}|{method}"]


def cell(a, s, market=BASE, method="lump_sum"):
    return next(c for c in heat(market, method) if c["a"] == a and c["s"] == s)


def strat(sid, market=BASE):
    return next(p for p in D()["scatter"][market] if p["id"] == sid)


def stress(st, sc, market=BASE):
    return next(r for r in D()["stress"] if r["market"] == market and r["st"] == st and r["sc"] == sc)


def guard(sc, g):
    return next(r for r in D()["guard"] if r["sc"] == sc and r["g"] == g)


def band(score):
    for b in D()["gl_bands"]:
        if b["lo"] <= score <= b["hi"]:
            return b["ko"]
    return "-"


def per100(x):
    """확률(%)을 일반인 표현으로."""
    if x <= 0:
        return "1만 번 중 0번"
    if x < 1:
        return f"1만 번 중 약 {round(x * 100)}번"
    return f"100번 중 약 {round(x)}번"


FACTS = """- 가구: A씨(1969년생, 2035년 은퇴), 배우자(1967년생, 2033년 은퇴), 아들(1999년생, 월 38.2만 원 지원, 45세까지), 양가 어머니(83세, 연 약 370만 원 지원)
- 최종안: 국민연금 A씨 70세·배우자 69세 연기수령(C48), 퇴직급여 둘 다 일시금, 투자 B00(예적금 27%+채권 73%, 주식 0%), 생활비 가드레일(연초 금융자산이 올해+내년 필수 순지출보다 적으면 생활비를 월 216.6만 원으로, 3년치 이상 회복되면 복귀)
- 몬테카를로 1만 경로 결과(2026년 가치): 기본 생활(최소 장부) 부족 0%, 지금 생활(월 295.8만 원) 유지 실패 0.00%, 100세 금융자산 중앙값 5.20억, 하위 5% 평균 3.30억
- 연금 공백기 2036~2039년: 4년간 인출 중앙값 약 1억 173만 원(명목), 2026년 가치 약 8,030만 원
- 정상 개시(65·64세)면 100세 중앙값 3.07억, 하위 5% 평균 1.15억. 둘 다 조기(60·59세)면 지금 생활 유지 실패 34.41%
- 국민연금 조정률(엔진 동일, 세전): 조기 월 0.5%(5년 −30%), 연기 월 0.6%(5년 +36%)
- B40(주식 약 29%): 중앙값 8.56억, 하위 5% 평균 4.05억, 변동성 7.09%(B00 2.76%), 은퇴 직후 폭락 시 하위 5% 평균 3.47억·실패 0.09%. 목표 달성률은 B00과 통계적 차이 없음
- 스트레스(B00): 5년 고물가(2027~2031 물가 5%) 시 실패 1.24% → 생활비 가드레일로 0%(약 1.3% 경로에서 평균 2.1년 사용). 가족 사건 최악·폭락 동시에도 실패 0%
- 토네이도: 생활비 월 ±30만 원 → 하위 5% 평균 +1.74/−1.63억, 국민연금 급여가 2위, 물가(금리 동반)는 ±0.2억
- 위험지표: 위험필요도 낮음(요구수익률 0%), 위험감수능력 보통(외부 재원 '있으나 불충분'은 페르소나 가정), G&L 23·26점은 페르소나 모의응답. 등급으로 주식 비중을 자동 변환하지 않음
- 한계: 부부 사망 미모델링(연기수령 이점이 실제보다 클 수 있음), 교육·공모전용 시뮬레이션"""
