import streamlit as st

import analytics as az

st.set_page_config(page_title="이효준 - 고객은 왜 이탈하는가", layout="wide")

st.title("이효준 — 고객은 왜 이탈하는가: 이커머스 CS 데이터 인사이트 대시보드")

data = az.load_data()
voc, cust, cons, sat, merged = data["voc"], data["cust"], data["cons"], data["sat"], data["merged"]

st.sidebar.markdown(
    "이 대시보드는 모두의연구소 2~3주차 프로젝트로 제작되었습니다.\n\n"
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

dash_tab, report_tab = st.tabs(["대시보드", "개선 제안 리포트"])

# ==================== 큰 탭 1: 대시보드 ====================
with dash_tab:
    overall = az.overall_churn_stats(cust)
    m0_1, m0_2, m0_3 = st.columns(3)
    m0_1.metric("전체 고객 수", f"{overall['total']}명")
    m0_2.metric("이탈 고객 수", f"{overall['churned']}명")
    m0_3.metric("전체 이탈율", f"{overall['rate']}%")

    st.info(
        "**핵심 요약(정직한 버전)**\n\n"
        "1. VOC: 결제/환불이 부정비율 최고(47.9%)이나, 카테고리 간 차이는 6.4%p로 크지 않음\n"
        "2. 만족도: NPS 평균(6.60)만 보면 무난하지만 정식 계산법으로는 -14.1 — '평균의 함정'은 재현됨\n"
        "3. 재문의·이탈: 반복재문의·회원등급·지역 신호는 이 합성 데이터에서 이탈과 뚜렷한 상관을 보이지 않음 "
        "(일부는 반대 방향) — 처방적 제안은 데이터 한계로 보류\n"
        "4. 상담원(3주차): eNPS는 -60.0으로 평균의 함정이 재현되나, 번아웃·교육이수와 고객경험의 상관관계는 "
        "통계적으로 유의하지 않음(r=-0.32, p=0.17 등). 근속기간을 통제하면 이 상관은 거의 사라져 — "
        "'번아웃'보다 '신입 온보딩 기간' 문제일 가능성"
    )

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["VOC 현황", "만족도", "재문의·이탈", "고객 현황", "상담원 관점"])

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

        st.plotly_chart(az.fig_voc_churn_history(voc, cust), use_container_width=True)
        st.caption("교안엔 '해지관련' VOC 대분류가 있지만 이 데이터엔 없어, 가장 가까운 소분류 '탈퇴 문의'(회원/계정)로 대체했다. "
                   "결과: 이력 있는 고객(n=13)의 이탈율(7.7%)이 전체 평균(11.3%)보다 오히려 낮음 — 반대 방향(표본이 작고 `churn_yn`이 VOC와 독립 생성된 데이터 한계).")

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

        st.plotly_chart(az.fig_channel_csat_recontact_combo(fm), use_container_width=True)
        st.caption("위 2개 단일축 차트가 더 읽기 쉽지만(2개 지표를 한 축에 겹치면 비교가 왜곡될 수 있음), "
                   "과제에서 요구하는 결합차트(dual-axis) 형태도 함께 남겨둔다.")

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

        map_event = st.plotly_chart(
            az.fig_region_map(cust), use_container_width=True,
            on_select="rerun", selection_mode="points", key="region_map",
        )
        points = map_event.selection.points if map_event and map_event.selection else []
        if points:
            region, count, churned, rate = points[0]["customdata"]
            m1, m2, m3 = st.columns(3)
            m1.metric(f"{region} 고객수", f"{count}명")
            m2.metric(f"{region} 이탈 고객수", f"{churned}명")
            m3.metric(f"{region} 이탈율", f"{rate}%")
        else:
            st.caption("지도의 버블을 클릭하면 해당 지역의 고객수·이탈 고객수·이탈율이 여기에 표시됩니다.")

        c3, c4 = st.columns(2)
        with c3:
            st.plotly_chart(az.fig_join_cohort(cust), use_container_width=True)
        with c4:
            st.plotly_chart(az.fig_age_dist(cust), use_container_width=True)

        st.plotly_chart(az.fig_tenure_usage_scatter(cust, data["usage"]), use_container_width=True)

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

    # ---------------- Tab 5: 상담원 관점 (3주차) ----------------
    with tab5:
        st.subheader("상담원 관점: 직원만족도와 고객 경험")

        agents = data["agents"]
        team_sel = st.selectbox("팀 필터", ["전체", "1팀", "2팀", "3팀"], key="agent_team_filter")
        fdf5 = az.filter_agents(agents, team_sel)
        st.caption(f"필터 적용 후 {len(fdf5)}명 (전체 {len(agents)}명)")
        if team_sel != "전체" and len(fdf5) < 10:
            st.warning(f"'{team_sel}'은 표본이 {len(fdf5)}명뿐입니다 — 아래 상관계수·비율은 참고용으로만 보세요.")

        c1, c2 = st.columns([1, 2])
        with c1:
            st.plotly_chart(az.fig_enps_gauge(fdf5), use_container_width=True)
        with c2:
            st.plotly_chart(az.fig_burnout_csat_scatter(fdf5), use_container_width=True)

        st.plotly_chart(az.fig_training_compare(fdf5), use_container_width=True)

        st.markdown(
            "**해석**: 직원만족도를 NPS 계산법 그대로 적용하면 eNPS가 크게 마이너스로 나오는 "
            "'평균의 함정'은 재현되지만(전체 -60.0), 번아웃-CSAT·만족도-재문의율 상관관계는 "
            "이 데이터에서 방향만 같고 통계적으로 유의하지 않다(r=-0.32, p=0.17 등)."
        )
        st.caption("신뢰도: 낮음 (가설) — 위 두 관계 자체의 confidence")

        st.markdown("---")
        st.subheader("근속기간(재직기간) 교란변수 분석")
        st.markdown(
            "근속기간이 만족도·초과근무·교육이수와 모두 매우 유의하게 연결돼 있다는 것을 "
            "**표와 그래프로 직접** 확인한다 — 리포트 텍스트로만 서술했던 근거를 여기서 재현한다."
        )

        corr_table = az.tenure_corr_table(fdf5)
        st.dataframe(corr_table, use_container_width=True, hide_index=True)

        c3, c4 = st.columns(2)
        with c3:
            st.plotly_chart(az.fig_tenure_satisfaction(fdf5), use_container_width=True)
        with c4:
            st.plotly_chart(az.fig_tenure_overtime(fdf5), use_container_width=True)

        c5, c6 = st.columns(2)
        with c5:
            st.plotly_chart(az.fig_tenure_by_training(fdf5), use_container_width=True)
        with c6:
            st.plotly_chart(az.fig_confound_comparison(fdf5), use_container_width=True)

        st.markdown(
            "**핵심 발견**: 근속기간이 만족도(r=0.86)·초과근무(r=-0.81)·교육이수(r=0.79)와 모두 p<0.0001로 "
            "강하게 연결돼 있다(위 표·산점도). 교육이수 여부별 근속기간 박스플롯을 보면 두 그룹이 근속기간으로 "
            "거의 완벽히 갈리는 것을 점 하나하나로 확인할 수 있다. 근속기간을 통제하면 번아웃-CSAT 상관은 "
            "-0.32→-0.13, 만족도-재문의율은 -0.29→+0.15(부호 역전)로 오른쪽 막대그래프처럼 거의 사라진다 — "
            "'번아웃 관리'보다 **'신입 온보딩 기간'** 문제일 가능성이 높다."
        )
        st.caption("신뢰도: 중간 (근속기간 교란변수 확인 자체는 높음, 고객지표로의 연결은 여전히 낮음) — 자세한 근거는 위키 이커머스_직원만족도_고객경험_상관관계_유의성부족 참고")

        st.markdown("---")
        st.subheader("이직(turnover) 위험과 근속기간 — 이번 분석에서 가장 유의한 발견")
        c7, _ = st.columns([1, 1])
        with c7:
            st.plotly_chart(az.fig_tenure_by_turnover(fdf5), use_container_width=True)
        st.markdown(
            "**핵심 발견**: 이직 여부는 근속기간과 **point-biserial r=-0.60 (p=0.005)** 로 유의하게 연결된다 "
            "(Mann-Whitney U 검정도 p=0.002로 일치). 이직자 3명(AG09·AG16·AG20)은 전원 근속 19~24개월인 반면, "
            "재직중인 상담원의 평균 근속은 51개월이다. 이번 상담원 분석 전체에서 **가장 통계적으로 확실한 신호**다."
        )
        st.markdown(
            "**추가 확인(QA 점수는 독립 신호가 아님)**: `qa_score`는 만족도(r=0.99)·초과근무(r=-0.97)·근속기간"
            "(r=0.86)과 거의 완벽히 겹친다 — 사실상 근속기간의 재진술이며, 향후 성과 스코어링에서 별도 가중치로 "
            "중복 반영하면 안 된다."
        )
        st.markdown(
            "**3팀 근속기간 직접 확인**: 3팀 평균 근속 39.3개월로 1팀(48.0)·2팀(51.3)보다 짧은 편이나, "
            "Kruskal-Wallis 검정 결과 팀 간 근속기간 차이 자체는 유의하지 않다(p=0.42) — '3팀에 신입이 많다'는 "
            "가설은 방향은 맞지만 아직 통계적으로 확정되지 않았다."
        )
        st.caption("신뢰도: 높음 (이직-근속기간 관계는 직접 검정으로 확인됨. n=20/이직 3명이라는 표본 자체의 한계는 여전히 존재)")

# ==================== 큰 탭 2: 개선 제안 리포트 ====================
with report_tab:
    try:
        with open("report/고객서비스_만족도개선_리포트.md", encoding="utf-8") as f:
            st.markdown(f.read())
    except FileNotFoundError:
        st.warning("report/고객서비스_만족도개선_리포트.md 파일을 찾을 수 없습니다.")
