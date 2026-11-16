# 노후나침반 (AFPK 공모전 팀_B안 웹)

A씨 가구 노후 재무설계 결과를 **설계사 화면**(재무설계 6단계 순서, 13페이지)과 **고객 화면**(일반인용, 8페이지)으로 보여주는 Streamlit 앱입니다.
숫자는 `afpk_simulation` 1만 경로 결과에서 뽑은 `data/results.json`을 씁니다.

## 실행

```powershell
cd 노후나침반_web
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

오른쪽 위 버튼으로 설계사/고객 화면을 바꿉니다. 고객 화면 주소(`/c-home`, `/c-life` …)로 바로 들어가도 됩니다.

## AI 상담 (선택)

`.streamlit/secrets.toml.example`을 `secrets.toml`로 복사하고 `OPENAI_API_KEY`를 넣으면 GPT가 답합니다. 키가 없으면 예시 답변만 나옵니다.
`secrets.toml`은 `.gitignore`로 제외되어 GitHub에 올라가지 않습니다. Streamlit Cloud에서는 앱 설정의 Secrets 칸에 같은 내용을 넣습니다.

- 고객용 AI: 계산 결과만 근거로 쉬운 말 설명, 상품 추천·권유 금지, 결정은 설계사 상담으로 안내
- 설계사용 AI: 수치와 근거(조합·전략·시장) 명시, 결과에 없는 조건은 "엔진 재계산 필요"

## 구조

```
app.py                 화면 전환 + 페이지 등록
core/data.py           결과 데이터 읽기, 공통 상수, AI 근거 요약(FACTS)
core/ui.py             토스 스타일 CSS·카드·표, Plotly 공통 스타일
core/charts.py         공용 그래프
core/risk.py           G&L 설문 상태, CFA·필요도 판정 (등급 → 주식 비중 자동 변환 안 함)
core/ai.py             GPT 연결, 고객 화면 '물어보기'
views/pro/*.py         설계사 화면
views/client/*.py      고객 화면
```

## 엔진 연결 (설계사 화면 「우리 집이라면?」)

- `afpk_simulation/` = 본실험 엔진 코드 복사본(테스트·스크립트·결과 폴더 제외). 엔진을 고치면 이 폴더도 다시 복사해야 함
- 연금 나이·퇴직급여·투자전략·시장만 바꾸면 `data/grid_lookup.json`(본실험 1만 경로 결과)을 바로 조회
- 생활비 금액·자녀 결혼·독립 지원 규모·생활비 가드레일을 바꾸면 엔진을 1,000경로로 실시간 계산(로컬 약 8초, Streamlit Cloud 약 1분)하고,
  추천안도 같은 경로·같은 난수로 계산해 비교. 같은 조건은 캐시
- 연결 코드: `core/engine_link.py`

## 아직 예시인 부분

- AI 상담은 키 연결 전까지 예시 답변
