"""모듈별 독립 RNG 스트림 파생.

하나의 master seed에서 재취업·부모·자녀·투자 RNG를 각각 파생한다.

파생 방식
- `random.Random(f"{master_seed}:{module_name}")`
- Python `random.Random`은 문자열 seed를 SHA-512로 변환해 사용하므로
  실행할 때마다(PYTHONHASHSEED와 무관하게) 같은 난수열이 재현된다.
- master seed와 모듈명이 문자열 안에서 함께 구분되므로,
  Monte Carlo에서 `master_seed = base_seed + path_index`로 seed를 증가시켜도
  서로 다른 path·모듈의 스트림이 겹치지 않는다.
  (작은 정수 offset 방식의 path 간 충돌 문제를 피한다.)
- Python 내장 `hash()`는 프로세스마다 값이 달라지므로 사용하지 않는다.

module_id는 문서화·검증용 고정 식별자다.
"""
from __future__ import annotations

import random

MODULE_IDS = {
    "reemployment": 1,
    "parent": 2,
    "child": 3,
    "investment": 4,
}

DERIVATION_METHOD = 'random.Random(f"{master_seed}:{module_name}")'


def validate_seed(master_seed):
    if master_seed is None:
        return
    if not isinstance(master_seed, int) or isinstance(master_seed, bool):
        raise TypeError("random_seed는 정수 또는 None이어야 합니다.")


def stream_key(master_seed, module_name):
    """해당 path·모듈 스트림을 식별하는 결정론적 seed 문자열."""
    if module_name not in MODULE_IDS:
        raise ValueError(f"정의되지 않은 RNG 모듈: {module_name}")
    validate_seed(master_seed)
    return f"{master_seed}:{module_name}"


def derive_rng(master_seed, module_name):
    """master seed에서 모듈 전용 random.Random 객체를 만든다.

    master_seed가 None이면 재현성이 없는 비고정 RNG를 반환한다.
    """
    key = stream_key(master_seed, module_name)
    if master_seed is None:
        return random.Random()
    return random.Random(key)
