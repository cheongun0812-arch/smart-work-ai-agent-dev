from __future__ import annotations

import pandas as pd
import streamlit as st

from ibex_parser import parse_waton_ibex

st.set_page_config(
    page_title="SMART WORK AI AGENT DEV",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
.stApp { background: #f4f7fb; }
.block-container { max-width: 1180px; padding-top: 1.8rem; padding-bottom: 4rem; }
.dev-badge { display:inline-block; background:#fff3cd; color:#7a5600; border:1px solid #f0d98b; padding:6px 12px; border-radius:999px; font-weight:800; font-size:.88rem; }
.hero { background:white; border:1px solid #dce4ef; padding:24px; border-radius:18px; box-shadow:0 6px 24px rgba(31,48,76,.06); margin:12px 0 18px; }
.hero h1 { margin:0 0 8px 0; font-size:2rem; }
.hero p { margin:0; color:#53657d; }
.safe-box { background:#edf8f0; border:1px solid #b9dfc3; border-radius:14px; padding:14px 16px; margin:8px 0 16px; }
.small-note { color:#6b7a90; font-size:.92rem; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<span class="dev-badge">개발용 · 운영 데이터 미연결</span>', unsafe_allow_html=True)
st.markdown(
    """
<div class="hero">
  <h1>🔋 SMART WORK AI AGENT · IBEX Pilot</h1>
  <p>WATON IBEX 원본 .xls 파일을 그대로 선택하면 Bank와 24 Cell 묶음을 자동 분석합니다.</p>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="safe-box"><b>안전 원칙</b><br>이 개발 앱은 Google Sheets에 저장하지 않습니다. 실제 운영 SMART WORK와도 연결되어 있지 않습니다.</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### DEV Control")
    st.caption("운영본과 분리된 IBEX 기능 검증용")
    st.markdown("- 원본 파일 변환 불필요\n- 24 Cell 자동 검증\n- 불완전 측정 자동 제외\n- 운영 DB 저장 없음")

uploaded = st.file_uploader(
    "IBEX 측정 파일 선택",
    type=["xls"],
    help="WATON IBEX에서 내보낸 원본 .xls 파일을 그대로 선택하세요.",
)

if uploaded is None:
    st.info("IBEX 원본 `.xls` 파일을 선택하면 분석을 시작합니다.")
    st.markdown("#### 이번 Pilot에서 확인할 내용")
    st.markdown(
        """
- WATON 원본 형식 자동 인식
- Bank별 24 Cell 측정 묶음 자동 분리
- 48 Cell 데이터의 1~24 / 25~48 자동 분리
- 전압 0.00V 또는 누락 Cell이 있는 묶음 자동 제외
- 전압 / 임피던스(Impe) / 온도 필드 확인
- 1조 또는 2조에 적용되는 형태 미리보기
"""
    )
    st.stop()

raw = uploaded.getvalue()
parsed = parse_waton_ibex(raw, uploaded.name)

if not parsed.get("recognized"):
    st.error(parsed.get("message", "지원하지 않는 파일 형식입니다."))
    st.stop()

if not parsed.get("ok"):
    st.warning(parsed.get("message", "파일을 자동 적용할 수 없습니다."))
    if parsed.get("diagnostics"):
        st.dataframe(pd.DataFrame(parsed["diagnostics"]), use_container_width=True, hide_index=True)
    st.stop()

st.success(parsed["message"])

c1, c2, c3 = st.columns(3)
c1.metric("파일", uploaded.name)
c2.metric("Export 시각", parsed.get("export_time") or "미확인")
c3.metric("측정 흔적 Bank", ", ".join(map(str, parsed.get("observed_banks", []))) or "-")

candidates = parsed["candidates"]
labels = [c["label"] for c in candidates]
selected_label = st.selectbox("가져올 IBEX 측정 묶음", labels)
selected = next(c for c in candidates if c["label"] == selected_label)

df = pd.DataFrame(selected["records"]).rename(
    columns={
        "cell": "Cell",
        "source_cell": "원본 Cell",
        "voltage": "전압(V)",
        "impedance": "임피던스(Impe)",
        "temperature": "온도(℃)",
    }
)

voltages = df["전압(V)"].astype(float)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Cell", f"{len(df)} / 24")
m2.metric("최저 전압", f"{voltages.min():.3f} V")
m3.metric("평균 전압", f"{voltages.mean():.3f} V")
m4.metric("최고 전압", f"{voltages.max():.3f} V")

st.markdown("### Cell 전압 분포")
chart_df = df.set_index("Cell")[["전압(V)"]]
st.bar_chart(chart_df, height=260)

st.markdown("### 측정값 확인")
show_cols = ["Cell", "원본 Cell", "전압(V)", "임피던스(Impe)", "온도(℃)"]
st.dataframe(df[show_cols], use_container_width=True, hide_index=True, height=520)

if parsed.get("incomplete_segments"):
    with st.expander("자동 적용에서 제외된 불완전 측정 보기"):
        st.caption("0.00V, 누락 Cell 등으로 24 Cell 자동 적용 조건을 충족하지 못한 묶음입니다.")
        st.dataframe(pd.DataFrame(parsed["incomplete_segments"]), use_container_width=True, hide_index=True)

st.markdown("### SMART WORK 적용 미리보기")
target_group = st.radio("적용 대상", ["1조", "2조"], horizontal=True)

preview = df[["Cell", "전압(V)"]].copy()
preview.insert(0, "적용 조", target_group)
preview["입력 결과"] = preview["전압(V)"].map(lambda v: f"{float(v):.3f}".rstrip("0").rstrip("."))

left, right = st.columns([1.2, 1])
with left:
    st.dataframe(preview[["적용 조", "Cell", "입력 결과"]], use_container_width=True, hide_index=True, height=430)
with right:
    st.markdown(
        f"""
**적용 시 동작**

`{target_group}`의 기존 Cell 1~24 입력칸에 아래 전압값이 자동으로 채워지는 구조입니다.

- 원본 Bank: **{selected['bank']}**
- 원본 범위: **Cell {selected['source_start']}~{selected['source_end']}**
- 적용 범위: **{target_group} Cell 1~24**
- Google Sheets 저장: **하지 않음 (DEV)**

현재 Pilot에서는 실제 운영 데이터에 쓰지 않고 **미리보기까지만** 합니다.
"""
    )

csv_bytes = df[show_cols].to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "정규화 CSV 다운로드",
    data=csv_bytes,
    file_name=f"IBEX_NORMALIZED_BANK{selected['bank']}_{selected['source_start']}_{selected['source_end']}.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption("SMART WORK AI AGENT DEV · WATON IBEX Pilot · 운영 환경과 분리")
