# SMART WORK AI AGENT DEV

운영 SMART WORK와 완전히 분리된 **개발/검증 전용 저장소**입니다.

## 현재 단계

WATON IBEX 원본 `.xls` 파일을 Streamlit에서 바로 읽어 다음을 검증합니다.

- `IBEX Impedance Data` 원본 형식 자동 인식
- Bank별 24 Cell 묶음 자동 탐색
- 48 Cell Bank의 `1~24`, `25~48` 자동 분리
- `0.00V`, 누락 Cell 등 불완전 데이터 자동 적용 제외
- Cell별 `Volt / Impe / Temp` 표시
- 1조 / 2조에 적용되는 형태 미리보기
- 정규화 CSV 다운로드

## 안전 원칙

- 운영 SMART WORK와 연결하지 않음
- 운영 Google Sheets에 저장하지 않음
- Streamlit Secrets를 GitHub에 저장하지 않음
- 제조사 Bluetooth Protocol 확인 전 임의 Bluetooth 명령을 보내지 않음

## Streamlit Community Cloud 배포

- Repository: `cheongun0812-arch/smart-work-ai-agent-dev`
- Branch: `main`
- Main file path: `app.py`

현재 Pilot은 별도 Secrets 없이 실행할 수 있습니다.

## 검증된 실제 샘플

`IBEX_20260903_094254.xls` 기준으로 다음 3개 자동 적용 후보가 확인되었습니다.

1. Bank 1 · Cell 1~24
2. Bank 2 · Cell 1~24
3. Bank 2 · Cell 25~48 → 현재 조 Cell 1~24

운영 반영은 개발 앱에서 충분히 검증한 뒤 진행합니다.
