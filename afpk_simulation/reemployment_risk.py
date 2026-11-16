"""KLoSA 표본수까지 반영한 재취업 확률 샘플링.

Beta(1,1) 사전분포 + KLoSA 성공/실패 관측을 사용한다.

관측값
- 2년 내 재취업: 여성 16/117, 남성 18/145
- 재취업 후 약 2년 시점 임금근로 유지: 여성 5/11, 남성 5/9
- 2년과 4년 모두 관측 가능한 표본 중 2년 임금근로자에서 4년까지 임금근로 지속:
  여성 2/2, 남성 1/3

주의
- KLoSA는 약 2년 간격 패널이므로 정확한 근속기간을 관측하는 자료가 아니다.
- 연 단위 현금흐름 엔진에 연결하기 위해 지속상태를 1/2/4년 bucket으로 번역한다.
  이 bucket은 '관측된 정확한 근속연수'가 아니라 모델링용 이산화다.
"""
from dataclasses import dataclass

from rng_streams import derive_rng


@dataclass(frozen=True)
class BetaBinomialEvidence:
    successes: int
    trials: int
    prior_alpha: float = 1.0
    prior_beta: float = 1.0

    @property
    def failures(self):
        return self.trials - self.successes

    @property
    def posterior_alpha(self):
        return self.prior_alpha + self.successes

    @property
    def posterior_beta(self):
        return self.prior_beta + self.failures

    def draw_probability(self, rng):
        return rng.betavariate(
            self.posterior_alpha,
            self.posterior_beta,
        )


KLOSA_REEMPLOYMENT_EVIDENCE = {
    "a": {
        "occurrence": BetaBinomialEvidence(16, 117),
        "retain_2y": BetaBinomialEvidence(5, 11),
        "extend_4y_given_2y": BetaBinomialEvidence(2, 2),
    },
    "spouse": {
        "occurrence": BetaBinomialEvidence(18, 145),
        "retain_2y": BetaBinomialEvidence(5, 9),
        "extend_4y_given_2y": BetaBinomialEvidence(1, 3),
    },
}


def _bernoulli(probability, rng):
    return rng.random() < probability


def sample_person_reemployment(person_key, rng):
    evidence = KLOSA_REEMPLOYMENT_EVIDENCE[person_key]

    p_occurrence = evidence["occurrence"].draw_probability(rng)
    success = _bernoulli(p_occurrence, rng)

    state = {
        "success": success,
        "duration_years": 0,
        "p_occurrence": p_occurrence,
        "p_retain_2y": None,
        "p_extend_4y_given_2y": None,
        "retained_2y": False,
        "extended_4y": False,
    }

    if not success:
        return state

    p_retain_2y = evidence["retain_2y"].draw_probability(rng)
    retained_2y = _bernoulli(p_retain_2y, rng)
    state["p_retain_2y"] = p_retain_2y
    state["retained_2y"] = retained_2y

    # 연 단위 엔진용 번역:
    # 2년 후 유지가 관측되지 않으면 1년 bucket,
    # 2년 후 유지되면 최소 2년 bucket으로 둔다.
    if not retained_2y:
        state["duration_years"] = 1
        return state

    p_extend_4y = evidence["extend_4y_given_2y"].draw_probability(rng)
    extended_4y = _bernoulli(p_extend_4y, rng)
    state["p_extend_4y_given_2y"] = p_extend_4y
    state["extended_4y"] = extended_4y
    state["duration_years"] = 4 if extended_4y else 2

    return state


def sample_household_reemployment(random_seed=None):
    """한 시뮬레이션 경로에서 개인별 재취업 상태를 한 번만 추출.

    master seed에서 파생한 재취업 전용 RNG 스트림을 사용한다(rng_streams.py).
    이 함수가 반환한 state를 cashflow·국민연금 adapter·세금 계산이 공유하며,
    각 모듈이 재취업 여부를 다시 추첨하지 않는다.
    """
    rng = derive_rng(random_seed, "reemployment")
    return {
        "a": sample_person_reemployment("a", rng),
        "spouse": sample_person_reemployment("spouse", rng),
    }
