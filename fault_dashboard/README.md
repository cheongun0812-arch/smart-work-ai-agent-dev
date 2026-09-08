# 2026 전원시설 장애 분석 대시보드

773건의 전원시설 장애와 처리결과를 Streamlit으로 조회·분석하는 내부 참고용 웹앱입니다.

## 주요 기능
- 9개 장애 대분류 대시보드
- 월별/지역별/유형별 통계
- 장애명·국사명·조치 상세 키워드 통합 검색
- 실제 과거 처리 상세 결과 조회
- 30일 이내 반복 장애 후보 조회
- 데이터 품질/추출 신뢰도 확인
- 모바일 반응형 UI

## 실행
```bash
cd fault_dashboard
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud 배포
1. GitHub 저장소를 Streamlit Community Cloud에 연결합니다.
2. Branch를 `feature/fault-dashboard-773`로 선택합니다. 검증 후 `main`에 병합해도 됩니다.
3. Main file path를 `fault_dashboard/app.py`로 지정합니다.
4. 배포합니다.

## 데이터
GitHub 배포용 데이터는 `data_parts/`의 텍스트 조각을 앱 시작 시 자동 복원합니다. 로컬 ZIP에는 원본 `data/incidents_773.csv`도 포함되어 있습니다.

## 주의
과거 장애 처리 결과는 참고자료입니다. 동일 알람이라도 현장 조건, 설비 구성, 작업 위험도가 다를 수 있으므로 사내 안전절차, 공식 작업표준, 제조사 매뉴얼을 우선합니다.
