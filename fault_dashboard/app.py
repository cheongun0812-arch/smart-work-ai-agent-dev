from __future__ import annotations

from pathlib import Path
import base64
import gzip
import html
import io
import re

import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "incidents_773.csv"
INFOGRAPHIC_PATH = BASE_DIR / "assets" / "infographic_web.jpg"

st.set_page_config(
    page_title="2026 전원시설 장애 분석",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CATEGORY_META = {
    "수배전/정전": {"icon": "⚡", "hint": "한전정전·자체정전·차단기/ACB 상태와 복전 여부를 우선 확인합니다."},
    "냉방/공조": {"icon": "❄️", "hint": "고온·누수·운전상태를 확인하고 설비 보호를 위한 긴급 냉방조치를 검토합니다."},
    "감시/통신": {"icon": "📡", "hint": "ELITE·MIH·L2/이더넷 통신상태, 접속 및 리셋 후 재발 여부를 확인합니다."},
    "정류/직류전원": {"icon": "🔌", "hint": "정류기 출력, 모듈/컨트롤러 상태, 접속 불량과 DC 출력 상태를 확인합니다."},
    "축전지/BIMS": {"icon": "🔋", "hint": "배터리 전압, 셀 편차, 단자 상태와 BIMS 통신/센서 상태를 확인합니다."},
    "청사환경/화재": {"icon": "🔥", "hint": "실제 화재·환경 이상과 감지기/센서 오동작을 구분하고 안전 절차를 우선합니다."},
    "기타": {"icon": "🧩", "hint": "동일 국사·유사 키워드의 과거 이력을 먼저 확인해 처리 패턴을 찾습니다."},
    "발전기": {"icon": "🛠️", "hint": "시동상태, 연료, 제어반, 배터리 및 자동운전 조건을 점검합니다."},
    "UPS/인버터": {"icon": "🔄", "hint": "인버터, 바이패스, 배터리 연계 상태와 입력/출력을 함께 확인합니다."},
}

CSS = """
<style>
:root { --navy:#102a43; --blue:#1f6fd2; --teal:#0f9d8a; --bg:#f4f7fb; --card:#ffffff; --line:#dbe5f0; }
.stApp { background: var(--bg); }
.block-container { max-width: 1440px; padding-top: 1.2rem; padding-bottom: 4rem; }
[data-testid="stSidebar"] { background: linear-gradient(180deg,#102a43 0%, #183b66 100%); }
[data-testid="stSidebar"] * { color: #f8fbff; }
.hero { background:linear-gradient(135deg,#ffffff 0%,#eff7ff 100%); border:1px solid var(--line); border-radius:20px; padding:24px 26px; box-shadow:0 8px 28px rgba(16,42,67,.06); margin-bottom:16px; }
.hero h1 { margin:0; color:#102a43; font-size:2rem; line-height:1.2; }
.hero p { margin:8px 0 0; color:#5c7089; }
.kpi { background:white; border:1px solid var(--line); border-radius:16px; padding:18px; min-height:126px; box-shadow:0 5px 18px rgba(16,42,67,.05); }
.kpi-label { color:#60758d; font-size:.9rem; font-weight:700; }
.kpi-value { color:#102a43; font-size:1.9rem; font-weight:900; margin-top:4px; }
.kpi-note { color:#75869a; font-size:.82rem; margin-top:4px; }
.section-card { background:white; border:1px solid var(--line); border-radius:18px; padding:18px; box-shadow:0 5px 18px rgba(16,42,67,.04); margin-bottom:14px; }
.guide-card { background:white; border:1px solid var(--line); border-radius:18px; padding:16px; height:100%; box-shadow:0 4px 14px rgba(16,42,67,.04); }
.guide-card .icon { font-size:2rem; }
.guide-card .name { color:#102a43; font-weight:900; font-size:1.05rem; margin-top:6px; }
.guide-card .count { color:#1f6fd2; font-weight:900; font-size:1.6rem; }
.guide-card .hint { color:#5f7186; font-size:.86rem; line-height:1.45; margin-top:6px; }
.result-card { background:white; border:1px solid #dce6f1; border-radius:16px; padding:16px 18px; margin:8px 0; box-shadow:0 4px 14px rgba(16,42,67,.04); }
.result-title { color:#102a43; font-size:1.04rem; font-weight:900; }
.result-meta { color:#64758a; font-size:.84rem; margin:3px 0 10px; }
.result-detail { background:#f7fafc; border-radius:12px; padding:12px; color:#324a61; font-size:.9rem; white-space:pre-wrap; line-height:1.55; }
.badge { display:inline-block; border-radius:999px; padding:3px 9px; font-size:.76rem; font-weight:800; margin-right:5px; background:#eaf2ff; color:#1d5cab; }
.warn { background:#fff8e7; border:1px solid #f0d48e; border-radius:14px; padding:12px 14px; color:#725513; font-size:.88rem; margin:8px 0 15px; }
.small { font-size:.82rem; color:#6f8094; }
@media (max-width: 760px) {
  .block-container { padding-left:.8rem; padding-right:.8rem; }
  .hero { padding:18px; }
  .hero h1 { font-size:1.55rem; }
  .kpi-value { font-size:1.5rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    if DATA_PATH.exists():
        df = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    else:
        part_dir = BASE_DIR / "data_parts"
        parts = sorted(part_dir.glob("data_part_*.txt"))
        if not parts:
            st.error("분석 데이터 파일을 찾을 수 없습니다.")
            st.stop()
        encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
        raw = gzip.decompress(base64.b64decode(encoded))
        df = pd.read_csv(io.BytesIO(raw), encoding="utf-8-sig")
    df["발생일시"] = pd.to_datetime(df["발생일시"], errors="coerce")
    if "최종근거시각" in df.columns:
        df["최종근거시각"] = pd.to_datetime(df["최종근거시각"], errors="coerce")
    for col in ["출동수", "댓글수(실측)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df["발생월"] = pd.to_numeric(df["발생월"], errors="coerce").fillna(df["발생일시"].dt.month).astype("Int64")
    df["검색문자열"] = (
        df[[
            "장애번호", "지역(국사명)", "장애(알람) 내용", "원인2(세부분류)",
            "조치(요약)=조치2", "장애대분류", "조치 상세 내용"
        ]]
        .fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    return df


def safe(value: object) -> str:
    if pd.isna(value):
        return "-"
    return html.escape(str(value))


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    out = df.groupby("장애대분류", dropna=False).size().reset_index(name="건수")
    out["비중"] = out["건수"] / len(df) * 100
    return out.sort_values("건수", ascending=False)


def search_incidents(df: pd.DataFrame, query: str, mode: str = "모든 단어 포함") -> pd.DataFrame:
    query = (query or "").strip().lower()
    if not query:
        return df.copy()
    tokens = [t for t in re.split(r"\s+", query) if t]
    if not tokens:
        return df.copy()
    masks = [df["검색문자열"].str.contains(re.escape(token), na=False) for token in tokens]
    mask = masks[0]
    for m in masks[1:]:
        mask = (mask & m) if mode == "모든 단어 포함" else (mask | m)
    return df[mask].copy()


def render_kpis(df: pd.DataFrame) -> None:
    total = len(df)
    comment_match = int((df["댓글수(실측)"] > 0).sum())
    dispatch = int((df["출동수"] > 0).sum())
    repeat = int(df["30일내 반복후보"].astype(str).str.contains("Y|예|1|True", case=False, regex=True).sum())
    cols = st.columns(4)
    cards = [
        ("총 장애", f"{total:,}건", "현재 확정 모집단"),
        ("댓글 매칭", f"{comment_match:,}건", "처리과정/근거댓글 확인 가능"),
        ("현장 출동", f"{dispatch:,}건 ({dispatch/total:.1%})", "출동수 > 0 기준"),
        ("30일 내 반복 후보", f"{repeat:,}건 ({repeat/total:.1%})", "동일·유사 장애 재발 후보"),
    ]
    for col, (label, value, note) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>',
                unsafe_allow_html=True,
            )


def render_category_cards(df: pd.DataFrame) -> None:
    summary = category_summary(df)
    total = len(df)
    rows = [summary.iloc[i:i+3] for i in range(0, len(summary), 3)]
    for chunk in rows:
        cols = st.columns(3)
        for idx, (_, row) in enumerate(chunk.iterrows()):
            cat = str(row["장애대분류"])
            meta = CATEGORY_META.get(cat, {"icon": "📌", "hint": "과거 장애 이력과 처리 결과를 확인합니다."})
            with cols[idx]:
                st.markdown(
                    f'''<div class="guide-card">
                    <div class="icon">{meta['icon']}</div>
                    <div class="name">{safe(cat)}</div>
                    <div class="count">{int(row['건수']):,}건 <span style="font-size:.9rem;color:#71849a">({row['건수']/total:.1%})</span></div>
                    <div class="hint">{safe(meta['hint'])}</div>
                    </div>''',
                    unsafe_allow_html=True,
                )


def render_result_cards(results: pd.DataFrame, max_items: int = 30) -> None:
    if results.empty:
        st.warning("검색 결과가 없습니다. 키워드를 줄이거나 '하나 이상 포함'으로 바꿔보세요.")
        return
    for _, row in results.head(max_items).iterrows():
        dt = row["발생일시"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["발생일시"]) else "-"
        title = safe(row["장애(알람) 내용"])
        detail = safe(row["조치 상세 내용"])
        meta = f"장애번호 {safe(row['장애번호'])} · {safe(row['지역(국사명)'])} · {dt}"
        badges = "".join([
            f'<span class="badge">{safe(row["장애대분류"])}</span>',
            f'<span class="badge">{safe(row["조치(요약)=조치2"])}</span>',
            f'<span class="badge">출동 {int(row["출동수"])}회</span>',
        ])
        st.markdown(
            f'''<div class="result-card">
            <div class="result-title">{title}</div>
            <div class="result-meta">{meta}</div>
            <div>{badges}</div>
            <div class="result-detail"><b>조치 상세</b>\n{detail}</div>
            </div>''',
            unsafe_allow_html=True,
        )


def page_dashboard(df: pd.DataFrame) -> None:
    st.markdown('<div class="hero"><h1>⚡ 2026 전원시설 장애 분석 대시보드</h1><p>2026-01-01 ~ 2026-08-31 · 최종 장애 773건 · 과거 장애와 처리 결과를 현장 참고용 지식으로 전환</p></div>', unsafe_allow_html=True)
    render_kpis(df)

    st.markdown("### 9개 장애 대분류")
    left, right = st.columns([1.0, 1.15])
    with left:
        cat = category_summary(df)
        fig = px.bar(cat.sort_values("건수"), x="건수", y="장애대분류", orientation="h", text="건수")
        fig.update_traces(textposition="outside")
        fig.update_layout(height=420, margin=dict(l=10,r=30,t=10,b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    with right:
        monthly = df.groupby("발생월").size().reindex(range(1,9), fill_value=0).reset_index(name="건수")
        monthly["월"] = monthly["발생월"].astype(str) + "월"
        fig = px.line(monthly, x="월", y="건수", markers=True, text="건수")
        fig.update_traces(textposition="top center")
        fig.update_layout(height=420, margin=dict(l=10,r=10,t=10,b=10), xaxis_title=None, yaxis_title="건")
        st.plotly_chart(fig, use_container_width=True)

    top3 = int(category_summary(df).head(3)["건수"].sum())
    summer = int(df[df["발생월"].isin([6,7,8])].shape[0])
    cooling = df[df["장애대분류"] == "냉방/공조"]
    cooling_dispatch = (cooling["출동수"] > 0).mean() if len(cooling) else 0
    c1,c2,c3 = st.columns(3)
    c1.info(f"**상위 3개 유형** · {top3:,}건 · 전체 {top3/len(df):.1%}")
    c2.info(f"**6~8월 집중** · {summer:,}건 · 전체 {summer/len(df):.1%}")
    c3.info(f"**냉방/공조 출동률** · {cooling_dispatch:.1%}")

    st.markdown("### 빠른 장애 검색")
    q = st.text_input("장애명·국사명·조치 키워드", placeholder="예: 냉방기 고온경보, ELITE 통신이상, 정류기 모듈, 냉매 주입", key="dashboard_search")
    if q.strip():
        results = search_incidents(df, q).sort_values("발생일시", ascending=False)
        st.caption(f"검색 결과 {len(results):,}건")
        render_result_cards(results, max_items=8)


def page_search(df: pd.DataFrame) -> None:
    st.title("🔎 장애 처리 결과 검색")
    st.caption("직원이 궁금한 장애명·설비·국사·조치 키워드로 773건의 과거 처리사례를 조회합니다.")
    st.markdown('<div class="warn"><b>안전 안내</b> · 아래 결과는 과거 이력 기반 참고자료입니다. 동일 알람이라도 현장 조건과 설비 상태가 다를 수 있으므로 사내 안전절차·작업표준·제조사 매뉴얼을 우선 적용하십시오.</div>', unsafe_allow_html=True)

    with st.container(border=True):
        q = st.text_input("키워드", placeholder="예: MIH L2, 냉방기 누수, 한전정전, 정류기 이상", key="main_search")
        f1,f2,f3,f4 = st.columns([1.2,1.2,1,1])
        with f1:
            category = st.multiselect("장애 대분류", sorted(df["장애대분류"].dropna().unique()))
        with f2:
            regions = st.multiselect("지역(국사명)", sorted(df["지역(국사명)"].dropna().unique()))
        with f3:
            months = st.multiselect("발생월", list(range(1,9)), format_func=lambda x: f"{x}월")
        with f4:
            mode = st.selectbox("검색 방식", ["모든 단어 포함", "하나 이상 포함"])
        dispatch_only = st.checkbox("현장 출동 발생 건만 보기")

    results = search_incidents(df, q, mode=mode)
    if category:
        results = results[results["장애대분류"].isin(category)]
    if regions:
        results = results[results["지역(국사명)"].isin(regions)]
    if months:
        results = results[results["발생월"].isin(months)]
    if dispatch_only:
        results = results[results["출동수"] > 0]
    results = results.sort_values("발생일시", ascending=False)

    st.markdown(f"#### 검색 결과 · {len(results):,}건")
    if len(results):
        top_actions = results["조치(요약)=조치2"].fillna("미등록").value_counts().head(5)
        st.caption("대표 조치: " + " · ".join([f"{k} {v}건" for k,v in top_actions.items()]))
    max_items = st.slider("화면 표시 건수", 10, 100, 30, step=10)
    render_result_cards(results, max_items=max_items)
    if len(results):
        export_cols = ["장애번호","발생일시","지역(국사명)","장애(알람) 내용","장애대분류","조치(요약)=조치2","조치 상세 내용","출동수","30일내 반복후보"]
        csv = results[export_cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button("검색 결과 CSV 다운로드", csv, file_name="장애_검색결과.csv", mime="text/csv")


def page_guides(df: pd.DataFrame) -> None:
    st.title("🧭 9대 장애 유형 가이드")
    st.caption("773건을 9개 대분류로 정리한 현장 학습·검색용 가이드입니다.")
    if INFOGRAPHIC_PATH.exists():
        st.image(str(INFOGRAPHIC_PATH), use_container_width=True)
    st.markdown("### 유형별 데이터 기반 대응 패턴")
    render_category_cards(df)

    st.divider()
    selected = st.selectbox("자세히 볼 유형", category_summary(df)["장애대분류"].tolist())
    sub = df[df["장애대분류"] == selected].copy()
    meta = CATEGORY_META.get(selected, {"hint":"과거 사례를 참고합니다."})
    st.info(meta["hint"])
    a,b = st.columns(2)
    with a:
        alarms = sub["원인2(세부분류)"].fillna("미분류").replace("", "미분류").value_counts().head(10).reset_index()
        alarms.columns = ["세부 알람", "건수"]
        fig = px.bar(alarms.sort_values("건수"), x="건수", y="세부 알람", orientation="h", text="건수", title="세부 알람 Top 10")
        fig.update_layout(height=420, margin=dict(l=10,r=20,t=50,b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    with b:
        actions = sub["조치(요약)=조치2"].fillna("미등록").replace("", "미등록").value_counts().head(10).reset_index()
        actions.columns = ["조치", "건수"]
        fig = px.bar(actions.sort_values("건수"), x="건수", y="조치", orientation="h", text="건수", title="대표 조치 Top 10")
        fig.update_layout(height=420, margin=dict(l=10,r=20,t=50,b=10), xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("#### 최근 실제 처리사례")
    render_result_cards(sub.sort_values("발생일시", ascending=False), max_items=10)


def page_regions(df: pd.DataFrame) -> None:
    st.title("📍 지역별 분석")
    st.caption("장애 빈도뿐 아니라 실제 출동 부담을 함께 확인합니다.")
    g = df.groupby("지역(국사명)").agg(장애건수=("장애번호","count"), 출동건수=("출동수", lambda s: int((s>0).sum()))).reset_index()
    g["출동률"] = g["출동건수"] / g["장애건수"]
    topn = st.slider("표시 지역 수", 10, 50, 20, step=5)
    top = g.sort_values("장애건수", ascending=False).head(topn)
    fig = px.bar(top.sort_values("장애건수"), x="장애건수", y="지역(국사명)", orientation="h", color="출동률", text="장애건수")
    fig.update_layout(height=max(450, topn*26), margin=dict(l=10,r=20,t=10,b=10), xaxis_title=None, yaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)
    top_display = top.copy()
    top_display["출동률(%)"] = (top_display["출동률"] * 100).round(1)
    st.dataframe(top_display.drop(columns=["출동률"]), use_container_width=True, hide_index=True)


def page_repeats(df: pd.DataFrame) -> None:
    st.title("🔁 반복 장애")
    st.caption("30일 이내 동일·유사 장애 재발 후보를 우선 점검해 근본원인 제거 대상을 찾습니다.")
    repeat_mask = df["30일내 반복후보"].astype(str).str.contains("Y|예|1|True", case=False, regex=True)
    rep = df[repeat_mask].sort_values(["지역(국사명)","발생일시"], ascending=[True,False])
    c1,c2,c3 = st.columns(3)
    c1.metric("반복 후보 장애", f"{len(rep):,}건")
    c2.metric("관련 지역", f"{rep['지역(국사명)'].nunique():,}곳")
    c3.metric("관련 유형", f"{rep['장애대분류'].nunique():,}개")
    if not rep.empty:
        region_counts = rep["지역(국사명)"].value_counts().head(15).reset_index()
        region_counts.columns=["지역","건수"]
        fig = px.bar(region_counts.sort_values("건수"), x="건수", y="지역", orientation="h", text="건수")
        st.plotly_chart(fig, use_container_width=True)
        render_result_cards(rep, max_items=50)
    else:
        st.info("현재 데이터에 반복 후보 표시가 없습니다.")


def page_quality(df: pd.DataFrame) -> None:
    st.title("🧪 데이터 품질")
    st.caption("분석 결과를 신뢰할 수 있도록 댓글 매칭·조치 상세·추출 신뢰도를 점검합니다.")
    total = len(df)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("전체", total)
    c2.metric("댓글 있음", int((df["댓글수(실측)"]>0).sum()))
    c3.metric("조치 상세 있음", int(df["조치 상세 내용"].fillna("").str.strip().ne("").sum()))
    high = int(df["추출신뢰도"].astype(str).str.contains("높|고|high", case=False, regex=True).sum())
    c4.metric("고신뢰 추출", high)
    st.markdown("#### 추출 신뢰도")
    conf = df["추출신뢰도"].fillna("미분류").value_counts().reset_index()
    conf.columns=["신뢰도","건수"]
    st.dataframe(conf, use_container_width=True, hide_index=True)
    st.markdown("#### 검토 필요 후보")
    review = df[(df["댓글수(실측)"]==0) | (df["조치 상세 내용"].fillna("").str.strip()=="") | (~df["추출신뢰도"].astype(str).str.contains("높|고|high", case=False, regex=True))]
    st.dataframe(review[["장애번호","발생일시","지역(국사명)","장애(알람) 내용","조치(요약)=조치2","조치 상세 내용","추출신뢰도","댓글수(실측)"]], use_container_width=True, hide_index=True, height=520)


df = load_data()

with st.sidebar:
    st.markdown("## ⚡ SMART WORK")
    st.caption("전원시설 장애 분석 · 2026")
    page = st.radio(
        "메뉴",
        ["종합 대시보드", "장애 검색", "9대 유형 가이드", "지역별 분석", "반복 장애", "데이터 품질"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("**데이터 기준**")
    st.caption("2026-01-01 ~ 2026-08-31\n\n최종 모집단 773건")
    st.markdown("**운영 원칙**")
    st.caption("과거 처리 이력은 참고자료이며 현장 안전절차와 공식 작업표준이 항상 우선입니다.")

if page == "종합 대시보드":
    page_dashboard(df)
elif page == "장애 검색":
    page_search(df)
elif page == "9대 유형 가이드":
    page_guides(df)
elif page == "지역별 분석":
    page_regions(df)
elif page == "반복 장애":
    page_repeats(df)
else:
    page_quality(df)

st.caption("SMART WORK AI AGENT · 전원시설 장애 분석 · 과거 이력 기반 현장 참고용")
