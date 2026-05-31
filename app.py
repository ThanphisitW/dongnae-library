import os
import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium

# ── 페이지 설정 ───────────────────────────────────────
st.set_page_config(
    layout="wide",
    page_title="동네 도서관",
    page_icon="📚"
)

# ── CSS ───────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

* { font-family: 'Noto Sans KR', sans-serif; }

/* 사이드바 */
[data-testid="stSidebar"] { background-color: #3F22EC; }
[data-testid="stSidebar"] * { color: #FAFAFA !important; }
[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.2); }
[data-testid="stSidebar"] .stRadio label {
    font-size: 15px;
    padding: 8px 12px;
    border-radius: 8px;
    transition: background 0.15s;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.12);
}

/* 정보 카드 (탭2, 탭3 공용) */
.lib-card {
    background: #ffffff;
    border: 1px solid #e8e8f0;
    border-radius: 14px;
    padding: 24px 28px;
    margin-top: 16px;
}
.lib-card-name {
    font-size: 20px;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 4px;
}
.lib-card-sub {
    font-size: 13px;
    color: #888;
    margin-bottom: 16px;
}
.lib-info-row {
    font-size: 14px;
    color: #444;
    padding: 4px 0;
    border-bottom: 1px solid #f0f0f5;
}
.lib-info-row:last-child { border-bottom: none; }
.lib-info-label {
    font-size: 11px;
    font-weight: 600;
    color: #aaa;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 2px;
}
.stat-pill {
    display: inline-block;
    background: #f4f0ff;
    color: #3F22EC;
    font-size: 13px;
    font-weight: 600;
    padding: 6px 14px;
    border-radius: 99px;
    margin-right: 8px;
    margin-bottom: 6px;
}
.visit-badge-yes {
    font-size: 12px;
    font-weight: 600;
    color: #FA58A7;
    background: #fff0f6;
    padding: 3px 10px;
    border-radius: 99px;
}
.visit-badge-no {
    font-size: 12px;
    color: #aaa;
    background: #f5f5f5;
    padding: 3px 10px;
    border-radius: 99px;
}
/* metric 카드 미세 조정 */
[data-testid="metric-container"] {
    background: #fafafa;
    border: 1px solid #ececf5;
    border-radius: 12px;
    padding: 16px;
}
</style>
""", unsafe_allow_html=True)

# ── session_state 초기화 ──────────────────────────────
if "visited" not in st.session_state:
    st.session_state["visited"] = set()
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# ── CSV 자동 탐색 ─────────────────────────────────────
@st.cache_data
def load_data():
    candidates = [
        "library.csv",                                      # Streamlit Cloud
        "부산광역시_도서관_정보.csv",                          # 한글 파일명 fallback
        "/content/library.csv",                            # Colab
        "/content/부산광역시_도서관_정보.csv",                 # Colab 한글
        "/content/drive/MyDrive/library.csv",              # Colab Drive
        "/content/drive/MyDrive/부산광역시_도서관_정보.csv",   # Colab Drive 한글
    ]
    for path in candidates:
        if os.path.exists(path):
            return pd.read_csv(path, encoding="utf-8")
    return None

df = load_data()
if df is None:
    st.error("부산광역시_도서관_정보.csv 파일을 찾을 수 없습니다. Colab에 업로드해주세요.")
    st.stop()

# ── Gemini 초기화 (Colab + Streamlit Cloud 둘 다 지원) ─
model = None
GEMINI_API_KEY = None
try:                                      # Streamlit Cloud Secrets
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass
if not GEMINI_API_KEY:
    try:                                  # Colab Secrets
        from google.colab import userdata
        GEMINI_API_KEY = userdata.get("GEMINI_API_KEY")
    except Exception:
        pass
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
    except Exception:
        pass

# ── 공통 유틸 ─────────────────────────────────────────
def clean(val):
    return "정보 없음" if str(val).strip() in ["-", "", "nan", "None"] else str(val)

# ── 사이드바 ──────────────────────────────────────────
# 로고 경로 우선순위 탐색
# Streamlit Cloud: 레포 루트에 있으면 바로 찾음
# Colab Drive: /content/drive/MyDrive/ 에서 찾음
LOGO_CANDIDATES = [
    "logo.png",
    "Dongnae.png",
    "/content/drive/MyDrive/logo.png",
    "/content/drive/MyDrive/Dongnae.png",
]
LOGO_PATH = next((p for p in LOGO_CANDIDATES if os.path.exists(p)), None)

with st.sidebar:
    if LOGO_PATH:
        st.image(LOGO_PATH, use_column_width=True)
    else:
        st.markdown("### 동네 도서관")

    st.divider()

    page = st.radio(
        label="메뉴",
        options=["부산 도서관 시각화", "도서관 맵", "도서관 리스트", "AI 사서"],
        label_visibility="collapsed",
    )


# ════════════════════════════════════════════════════════
# 탭1: 부산 도서관 시각화
# ════════════════════════════════════════════════════════
if page == "부산 도서관 시각화":
    st.header("부산광역시 도서관")
    st.divider()

    # 데이터 계산 — 하드코딩 금지
    total_count     = len(df)
    gugun_count     = df["gugun"].nunique()
    category_counts = df["category"].value_counts()
    gugun_counts    = df["gugun"].value_counts().reset_index()
    gugun_counts.columns = ["gugun", "count"]
    top_seat_row    = df.loc[df["seat"].idxmax()]
    top_books_row   = df.loc[df["books"].idxmax()]
    top5_seat       = df.nlargest(5, "seat")[["library_na", "seat"]].reset_index(drop=True)

    # metric 3개
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("총 도서관 수", f"{total_count}개",
                  delta=f"부산 {gugun_count}개 구/군")
    with c2:
        st.metric("최대 좌석",
                  f"{int(top_seat_row['seat']):,}석",
                  delta=top_seat_row["library_na"])
    with c3:
        st.metric("최대 장서",
                  f"{int(top_books_row['books']):,}권",
                  delta=top_books_row["library_na"])

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("유형별 비율")
        pct_labels = [
            f"{name}  {cnt}개 ({cnt/total_count*100:.0f}%)"
            for name, cnt in category_counts.items()
        ]
        fig_donut = px.pie(
            values=category_counts.values,
            names=pct_labels,
            hole=0.5,
            color_discrete_sequence=["#3F22EC", "#818CF8", "#C7D2FE"],
        )
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20, l=0, r=0),
            height=320,
            font=dict(family="Noto Sans KR"),
            annotations=[dict(
                text=f"<b>{total_count}</b>",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20),
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_right:
        st.subheader("구별 도서관 수")
        fig_gugun = px.bar(
            gugun_counts.sort_values("count", ascending=True),
            x="count", y="gugun",
            orientation="h",
            color="count",
            color_continuous_scale=["#C7D2FE", "#3F22EC"],
            text="count",
            labels={"count": "도서관 수", "gugun": "구/군"},
        )
        fig_gugun.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
            height=480,
            margin=dict(t=20, b=0, l=0, r=40),
            font=dict(family="Noto Sans KR"),
        )
        st.plotly_chart(fig_gugun, use_container_width=True)

    st.divider()

    st.subheader("좌석수 TOP 5")
    fig_top5 = px.bar(
        top5_seat,
        x="seat", y="library_na",
        orientation="h",
        color="seat",
        color_continuous_scale=["#e8e0ff", "#3F22EC"],
        text="seat",
        labels={"seat": "좌석 수", "library_na": "도서관"},
    )
    fig_top5.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(autorange="reversed"),
        coloraxis_showscale=False,
        height=280,
        margin=dict(t=20, b=0, l=0, r=60),
        font=dict(family="Noto Sans KR"),
    )
    st.plotly_chart(fig_top5, use_container_width=True)


# ════════════════════════════════════════════════════════
# 탭2: 도서관 맵
# ════════════════════════════════════════════════════════
elif page == "도서관 맵":
    st.header("도서관 맵")
    st.caption("마커를 클릭하면 도서관 정보가 표시됩니다")

    center_lat = df["lat"].mean()
    center_lng = df["lng"].mean()

    m = folium.Map(location=[center_lat, center_lng], zoom_start=12,
                   tiles="CartoDB positron")  # 깔끔한 밝은 지도 타일

    for _, row in df.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=6,
            color="#3F22EC",
            fill=True,
            fill_color="#3F22EC",
            fill_opacity=0.75,
            weight=1.5,
            tooltip=row["library_na"],
        ).add_to(m)

    map_data = st_folium(m, use_container_width=True, height=460,
                         returned_objects=["last_object_clicked"])

    # 클릭 → 정보 카드 (이모지 없이 깔끔하게)
    if map_data and map_data.get("last_object_clicked"):
        clat = map_data["last_object_clicked"]["lat"]
        clng = map_data["last_object_clicked"]["lng"]
        df["_dist"] = ((df["lat"] - clat) ** 2 + (df["lng"] - clng) ** 2) ** 0.5
        sel = df.loc[df["_dist"].idxmin()]

        hp = clean(sel["homepage"])
        hp_html = f'<a href="{hp}" target="_blank" style="color:#3F22EC">{hp}</a>' \
                  if hp.startswith("http") else hp

        st.markdown(f"""
<div class="lib-card">
  <div style="display:flex; justify-content:space-between; align-items:flex-start">
    <div>
      <div class="lib-card-name">{sel['library_na']}</div>
      <div class="lib-card-sub">{sel['gugun']} &nbsp;·&nbsp; {sel['category']}</div>
    </div>
    <div>
      <span class="stat-pill">좌석 {int(sel['seat']):,}석</span>
      <span class="stat-pill">장서 {int(sel['books']):,}권</span>
    </div>
  </div>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 24px; margin-top:12px">
    <div>
      <div class="lib-info-label">평일</div>
      <div class="lib-info-row">{clean(sel['week_start'])} – {clean(sel['week_end'])}</div>
    </div>
    <div>
      <div class="lib-info-label">토요일</div>
      <div class="lib-info-row">{clean(sel['sat_start'])} – {clean(sel['sat_end'])}</div>
    </div>
    <div>
      <div class="lib-info-label">공휴일</div>
      <div class="lib-info-row">{clean(sel['holi_start'])} – {clean(sel['holi_end'])}</div>
    </div>
    <div>
      <div class="lib-info-label">휴관일</div>
      <div class="lib-info-row">{clean(sel['Close_day'])}</div>
    </div>
    <div>
      <div class="lib-info-label">전화</div>
      <div class="lib-info-row">{clean(sel['tel'])}</div>
    </div>
    <div>
      <div class="lib-info-label">홈페이지</div>
      <div class="lib-info-row">{hp_html}</div>
    </div>
    <div style="grid-column:1/-1">
      <div class="lib-info-label">주소</div>
      <div class="lib-info-row">{clean(sel['address'])}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.info("지도에서 도서관 마커를 클릭하면 상세 정보가 표시됩니다.")


# ════════════════════════════════════════════════════════
# 탭3: 도서관 리스트
# ════════════════════════════════════════════════════════
elif page == "도서관 리스트":
    st.header("도서관 리스트")

    # 필터 옵션 동적 추출 — 휴관일 제거, 장서 수 추가
    gugun_options    = sorted(df["gugun"].unique().tolist())
    category_options = sorted(df["category"].unique().tolist())
    seat_min  = int(df["seat"].min())
    seat_max  = int(df["seat"].max())
    books_min = int(df["books"].min())
    books_max = int(df["books"].max())

    with st.expander("필터", expanded=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            sel_gugun = st.multiselect("구/군", options=gugun_options)
            sel_cat   = st.multiselect("유형", options=category_options)
        with f2:
            sel_seat  = st.slider("좌석 수 범위",
                                   seat_min, seat_max, (seat_min, seat_max))
            sel_books = st.slider("장서 수 범위",
                                   books_min, books_max, (books_min, books_max))
        with f3:
            sel_visit = st.selectbox("방문 여부",
                                      ["전체", "가본 곳", "아직 안 가본 곳"])

    # 필터 적용
    filtered = df.copy()
    if sel_gugun: filtered = filtered[filtered["gugun"].isin(sel_gugun)]
    if sel_cat:   filtered = filtered[filtered["category"].isin(sel_cat)]
    filtered = filtered[
        (filtered["seat"]  >= sel_seat[0])  & (filtered["seat"]  <= sel_seat[1]) &
        (filtered["books"] >= sel_books[0]) & (filtered["books"] <= sel_books[1])
    ]
    if sel_visit == "가본 곳":
        filtered = filtered[filtered["library_na"].isin(st.session_state["visited"])]
    elif sel_visit == "아직 안 가본 곳":
        filtered = filtered[~filtered["library_na"].isin(st.session_state["visited"])]

    st.caption(f"총 {len(filtered)}개 도서관")
    st.divider()

    if filtered.empty:
        st.info("조건에 맞는 도서관이 없습니다.")
    else:
        for _, row in filtered.iterrows():
            lib_name   = row["library_na"]
            is_visited = lib_name in st.session_state["visited"]
            badge_html = '<span class="visit-badge-yes">가봤다</span>' \
                         if is_visited else \
                         '<span class="visit-badge-no">아직 안 가봄</span>'

            # expander 헤더: 이름 + 구/군 · 유형 + 방문뱃지
            with st.expander(
                f"{lib_name}  ·  {row['gugun']} / {row['category']}"
            ):
                hp = clean(row["homepage"])
                hp_html = f'<a href="{hp}" target="_blank" style="color:#3F22EC">{hp}</a>' \
                          if hp.startswith("http") else hp

                # 카드 HTML
                st.markdown(f"""
<div class="lib-card" style="margin-top:0">
  <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px">
    <div>
      <div class="lib-card-name">{lib_name}</div>
      <div class="lib-card-sub">{row['gugun']} &nbsp;·&nbsp; {row['category']}</div>
    </div>
    <div style="text-align:right">
      {badge_html}
      <div style="margin-top:8px">
        <span class="stat-pill">좌석 {int(row['seat']):,}석</span>
        <span class="stat-pill">장서 {int(row['books']):,}권</span>
      </div>
    </div>
  </div>
  <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px 24px">
    <div>
      <div class="lib-info-label">평일</div>
      <div class="lib-info-row">{clean(row['week_start'])} – {clean(row['week_end'])}</div>
    </div>
    <div>
      <div class="lib-info-label">토요일</div>
      <div class="lib-info-row">{clean(row['sat_start'])} – {clean(row['sat_end'])}</div>
    </div>
    <div>
      <div class="lib-info-label">공휴일</div>
      <div class="lib-info-row">{clean(row['holi_start'])} – {clean(row['holi_end'])}</div>
    </div>
    <div>
      <div class="lib-info-label">전화</div>
      <div class="lib-info-row">{clean(row['tel'])}</div>
    </div>
    <div style="grid-column:1/-1">
      <div class="lib-info-label">홈페이지</div>
      <div class="lib-info-row">{hp_html}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

                # 방문 체크 + 기록 남기기
                col_chk, col_diary = st.columns([1, 2])
                with col_chk:
                    visited_check = st.checkbox(
                        "가본 곳으로 저장",
                        value=is_visited,
                        key=f"visited_{lib_name}",
                    )
                    if visited_check:
                        st.session_state["visited"].add(lib_name)
                    else:
                        st.session_state["visited"].discard(lib_name)

                with col_diary:
                    if is_visited:
                        if st.button("기록 남기기", key=f"diary_btn_{lib_name}"):
                            st.session_state[f"diary_open_{lib_name}"] = \
                                not st.session_state.get(f"diary_open_{lib_name}", False)
                    else:
                        st.button("기록 남기기 (방문 후 사용 가능)",
                                  disabled=True, key=f"diary_btn_off_{lib_name}")

                if st.session_state.get(f"diary_open_{lib_name}"):
                    diary = st.text_area(
                        "이 도서관에서 어떤 시간을 보냈나요?",
                        value=st.session_state.get(f"diary_{lib_name}", ""),
                        placeholder="기억에 남는 순간을 기록해보세요",
                        key=f"diary_text_{lib_name}",
                    )
                    if st.button("저장", key=f"diary_save_{lib_name}"):
                        st.session_state[f"diary_{lib_name}"] = diary
                        st.success("기록이 저장됐어요.")

                if st.session_state.get(f"diary_{lib_name}"):
                    st.caption(f"기록 — {st.session_state[f'diary_{lib_name}']}")


# ════════════════════════════════════════════════════════
# 탭4: AI 사서
# ════════════════════════════════════════════════════════
elif page == "AI 사서":
    st.header("무엇이든 물어보세요")

    if model is None:
        st.warning("GEMINI_API_KEY가 Colab Secrets에 설정되지 않았습니다.")

    def build_system_prompt(df):
        cols = ["library_na", "gugun", "category", "seat", "books",
                "week_start", "week_end", "sat_start", "sat_end",
                "Close_day", "address"]
        df_text = df[cols].to_string(index=False)
        return f"""당신은 부산광역시 도서관 안내 AI 사서입니다.
아래는 실제 CSV에서 읽어온 부산 도서관 데이터입니다 (총 {len(df)}개):

{df_text}

규칙:
- 한국어로 친절하게 답변
- 도서관 추천 시 이름, 위치, 좌석 수, 운영시간 포함
- 데이터에 없는 내용은 "정보가 없습니다"로 답변
- 답변은 간결하게 유지"""

    col1, col2 = st.columns(2)
    with col1:
        if st.button("좌석 많은 도서관 TOP3 추천"):
            st.session_state["shortcut"] = \
                "좌석이 많고 접근성 좋은 도서관 TOP3를 이유와 함께 추천해줘"
    with col2:
        if st.button("장서 많은 공공도서관 찾기"):
            st.session_state["shortcut"] = \
                "공공도서관 중 장서가 가장 많은 곳 TOP3를 알려줘"

    st.divider()

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("도서관에 대해 궁금한 것을 입력하세요")

    if "shortcut" in st.session_state and st.session_state["shortcut"]:
        user_input = st.session_state.pop("shortcut")

    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        st.session_state["chat_history"].append({"role": "user", "content": user_input})

        if model:
            try:
                full_prompt = build_system_prompt(df) + f"\n\n사용자 질문: {user_input}"
                with st.chat_message("assistant"):
                    with st.spinner("답변을 준비 중입니다..."):
                        response = model.generate_content(full_prompt)
                        answer = response.text
                    st.markdown(answer)
                st.session_state["chat_history"].append(
                    {"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"AI 응답 오류: {e}")
        else:
            with st.chat_message("assistant"):
                st.warning("API 키를 설정하면 AI 사서를 사용할 수 있어요.")

        if len(st.session_state["chat_history"]) > 20:
            st.session_state["chat_history"] = st.session_state["chat_history"][-20:]
