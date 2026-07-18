import streamlit as st

import analytics as az

st.set_page_config(page_title="CS 데이터 인사이트 대시보드", layout="wide")

st.title("이커머스 CS 데이터 인사이트 대시보드")

st.info(
    "**이번 2주차 핵심 요약(정직한 버전)**\n\n"
    "1. VOC: 결제/환불이 부정비율 최고(47.9%)이나, 카테고리 간 차이는 6.4%p로 크지 않음\n"
    "2. 만족도: NPS 평균(6.60)만 보면 무난하지만 정식 계산법으로는 -14.1 — '평균의 함정'은 재현됨\n"
    "3. 재문의·이탈: 반복재문의·회원등급·지역 신호는 이 합성 데이터에서 이탈과 뚜렷한 상관을 보이지 않음 "
    "(일부는 반대 방향) — 처방적 제안은 데이터 한계로 보류"
)

data = az.load_data()
voc, cust, cons, sat, merged = data["voc"], data["cust"], data["cons"], data["sat"], data["merged"]

st.sidebar.markdown(
    "이 대시보드는 모두의연구소 2주차 프로젝트로 제작되었습니다.\n\n"
    "`raw/`의 데이터는 **100% 가상(합성) 이커머스 CS 데이터**이며, "
    "실제 서비스 데이터가 아닙니다. 일부 탭의 결과는 노이즈성이거나 "
    "예상과 반대 방향으로 나왔고, 이를 숨기지 않고 그대로 표시합니다."
)

st.sidebar.header("필터")
min_date = min(voc["접수일시"].min().date(), cons["consult_date"].min().date())
max_date = max(voc["접수일시"].max().date(), cons["consult_date"].max().date())
date_range = st.sidebar.date_input("기간", value=(min_date, max_date), min_value=min_date, max_value=max_date)
if len(date_range) != 2:
    date_range = (min_date, max_date)

voc_categories = st.sidebar.multiselect("VOC 대분류 (VOC 현황 탭)", sorted(voc["대분류"].unique()))
voc_channels = st.sidebar.multiselect("VOC 채널 (VOC 현황 탭)", sorted(voc["채널"].unique()))
cons_channels = st.sidebar.multiselect("상담 채널 (만족도·재문의 탭)", sorted(cons["channel"].unique()))

tab1, tab2, tab3, tab4 = st.tabs(["VOC 현황", "만족도", "재문의·이탈", "고객 현황"])

# ---------------- Tab 1: VOC 현황 ----------------
with tab1:
    fdf = az.filter_voc(voc, date_range, voc_categories, voc_channels)
    st.caption(f"필터 적용 후 {len(fdf)}건 (전체 {len(voc)}건)")

    st.plotly_chart(az.fig_voc_category(fdf), use_container_width=True)
    st.plotly_chart(az.fig_voc_monthly(fdf), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(az.fig_voc_channel_count(fdf), use_container_width=True)
    with c2:
        st.plotly_chart(az.fig_voc_channel_negrate(fdf), use_container_width=True)

    st.plotly_chart(az.fig_voc_sentiment_donut(fdf), use_container_width=True)

    st.subheader("대분류별 소분류 분해")
    cat_options = sorted(fdf["대분류"].unique()) if len(fdf) else sorted(voc["대분류"].unique())
    default_idx = cat_options.index("결제/환불") if "결제/환불" in cat_options else 0
    bc1, bc2 = st.columns(2)
    with bc1:
        sel_cat = st.selectbox("대분류 선택", cat_options, index=default_idx)
    with bc2:
        sel_senti = st.selectbox("감정분류", ["부정", "중립", "긍정", "전체"], index=0)
    st.plotly_chart(az.fig_voc_breakdown(fdf, sel_cat, sel_senti), use_container_width=True)

    with st.expander("🔍 드릴다운: 원문 문의내용 조회"):
        sub = fdf[fdf["대분류"] == sel_cat]
        if sel_senti != "전체":
            sub = sub[sub["감정분류"] == sel_senti]
        subcat_options = ["전체"] + sorted(sub["소분류"].unique().tolist())
        sel_subcat = st.selectbox("소분류로 더 좁히기", subcat_options)
        if sel_subcat != "전체":
            sub = sub[sub["소분류"] == sel_subcat]
        cols = ["접수일시", "채널", "소분류", "감정분류", "긴급도", "문의내용", "만족도점수(CSAT)"]
        st.dataframe(sub[cols].sort_values("접수일시", ascending=False), use_container_width=True, hide_index=True)

    st.markdown("**해석**: 대분류 간 부정 비율 차이가 크지 않다는 것 자체가, 특정 카테고리 하나의 문제가 아니라 부정 여론이 고르게 분포한다는 신호로 보인다.")
    st.markdown("**시사점**: 결제/환불을 하나로 뭉뚱그리지 않고 쿠폰/포인트·결제오류·이중결제·환불속도·부분환불 정책을 개별 과제로 분리해 개선하는 것이 효과적일 것으로 보인다.")
    st.caption("신뢰도: 높음 (데이터 직접 확인)")

# ---------------- Tab 2: 만족도 ----------------
with tab2:
    fm = az.filter_merged(merged, date_range, cons_channels)
    st.caption(f"필터 적용 후 상담 {len(fm)}건 (전체 {len(merged)}건)")

    sc = az.scorecard(fm)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CSAT 평균", f"{sc['csat_mean']} / 5")
    m2.metric("NPS 평균", f"{sc['nps_mean']} / 10", help="참고용(평균 지표) — 평균의 함정 주의")
    m3.metric("NPS 점수", sc["nps_score"], help="추천자%-비판자% (정식 계산)")
    m4.metric("저만족 비율", f"{sc['low_ratio']}%", help="CSAT 1~2점 비중")

    st.plotly_chart(az.fig_csat_by_category(fm), use_container_width=True)
    st.plotly_chart(az.fig_csat_hist(fm), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(az.fig_channel_csat(fm), use_container_width=True)
    with c2:
        st.plotly_chart(az.fig_channel_recontact(fm), use_container_width=True)

    with st.expander("🔍 드릴다운: 저만족(CSAT 1~2점) 상담 코멘트 조회"):
        cat_options = ["전체"] + sorted(fm["category"].dropna().unique().tolist())
        sel_cat2 = st.selectbox("카테고리로 좁히기", cat_options, key="low_csat_cat")
        low = az.drilldown_low_csat(fm, None if sel_cat2 == "전체" else sel_cat2)
        st.dataframe(low, use_container_width=True, hide_index=True)

    st.markdown("**해석**: NPS 평균의 함정은 재현되지만(6.60 → 정식계산 -14.1), 채널·카테고리별 효과는 텔레콤 원본만큼 뚜렷하지 않다 — 데이터가 상담 status에서만 파생되고 channel/category와 독립 생성된 한계로 판단.")
    st.markdown("**시사점**: 이 데이터로 '어느 채널을 우선 개선해야 하는가'를 확정하기는 어렵다. 다만 평균만 보고 안심하면 안 된다는 방법론적 교훈은 유효하다.")
    st.caption("신뢰도: 중간 (패턴 추정)")

# ---------------- Tab 3: 재문의·이탈 ----------------
with tab3:
    st.plotly_chart(az.fig_chain(merged, date_range, cons_channels), use_container_width=True)
    st.plotly_chart(az.fig_recontact_monthly(cons, date_range, cons_channels), use_container_width=True)

    with st.expander("🔍 드릴다운: 재문의 구간별 고객 목록"):
        bucket_sel = st.selectbox("구간 선택", ["재문의 없음", "재문의 1회", "재문의 2회+"])
        st.dataframe(az.drilldown_chain_customers(merged, date_range, cons_channels, bucket_sel),
                     use_container_width=True, hide_index=True)

    st.markdown("**해석**: 반복재문의(2회+) 고객의 이탈율(3.0%)이 재문의 없는 고객(13.5%)보다 오히려 낮게 나와, 텔레콤 원본과 반대 방향이다. `churn_yn`이 상담 이력과 독립적으로 생성된 데이터 한계로 판단된다.")
    st.markdown("**시사점**: 이 결과를 실제 비즈니스 결론으로 사용하면 안 된다. 체인 분석 방법론 자체(횟수로 쪼개서 보기)는 유효하다.")
    st.caption("신뢰도: 낮음 (가설 — 데이터 한계로 판단)")

# ---------------- Tab 4: 고객 현황 ----------------
with tab4:
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(az.fig_grade_churn(cust), use_container_width=True)
    with c2:
        st.plotly_chart(az.fig_region_churn(cust), use_container_width=True)

    st.plotly_chart(az.fig_region_map(cust), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(az.fig_join_cohort(cust), use_container_width=True)
    with c4:
        st.plotly_chart(az.fig_age_dist(cust), use_container_width=True)

    with st.expander("🔍 드릴다운: 고객 목록 조회"):
        d1, d2 = st.columns(2)
        with d1:
            grade_sel = st.multiselect("회원등급", sorted(cust["membership_grade"].unique()))
        with d2:
            region_sel = st.multiselect("지역", sorted(cust["region"].unique()))
        st.dataframe(az.drilldown_customers(cust, grade_sel, region_sel), use_container_width=True, hide_index=True)

    st.markdown("**해석**: 회원등급별 이탈율 차이는 4.6%p로 작고 VIP가 BRONZE보다 높게 나오는 등 상식과 다른 방향. 지역은 제주(n=30)를 제외한 전 지역이 표본 30건 미만이라 참고용에 그친다.")
    st.markdown("**시사점**: 등급·지역을 위험 신호로 사용하기에는 근거가 약하다. 규칙 기반 위험 스코어링도 신호 간 방향이 엇갈려(반복재문의가 반대 방향) 합산 점수가 작동하지 않음을 확인했다 — 처방적 제안(Top3)은 데이터 한계로 보류한다.")
    st.caption("신뢰도: 낮음 (가설 — 표본·데이터 생성 한계)")
