
from datetime import date


def generate_monthly_timeline(
    start_year=2026,
    end_year=2069
):
    """
    시작연도 1월부터 종료연도 12월까지
    월별 날짜를 생성한다.
    """
    timeline = []

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            timeline.append(date(year, month, 1))

    return timeline


if __name__ == "__main__":
    timeline = generate_monthly_timeline()

    print("전체 계산 개월 수:", len(timeline))
    print("첫 번째 월:", timeline[0])
    print("마지막 월:", timeline[-1])
