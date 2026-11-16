
from dataclasses import dataclass
from typing import Literal


PayoutMethod = Literal["lump_sum", "annuity"]


@dataclass(frozen=True)
class PayoutStrategy:
    a_method: PayoutMethod = "lump_sum"
    spouse_method: PayoutMethod = "lump_sum"

    def method_for(self, person_key: str):
        if person_key == "a":
            method = self.a_method

        elif person_key == "spouse":
            method = self.spouse_method

        else:
            raise ValueError(
                f"알 수 없는 사람: {person_key}"
            )

        if method not in ("lump_sum", "annuity"):
            raise ValueError(
                f"지원하지 않는 수령 방식: {method}"
            )

        return method
