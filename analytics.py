# -*- coding: utf-8 -*-
"""필터(기간·카테고리·채널)에 따라 즉시 재계산되는 Plotly 차트 모음.
기존 components/*.py(정적 PNG 생성)와 달리, 여기 함수들은 필터링된 DataFrame을 받아
매 요청마다 새로 그린다 — Streamlit이 요청마다 스크립트를 재실행하는 구조이기 때문에 가능하다.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from scipy import stats

RAW = "raw"

# dataviz 스킬 검증 팔레트(카테고리 순서 고정) + 상태색(good/critical)
BLUE, GREEN, MAGENTA, YELLOW, AQUA, ORANGE, VIOLET, RED = (
    "#2a78d6", "#008300", "#e87ba4", "#eda100", "#1baf7a", "#eb6834", "#4a3aa7", "#e34948",
)
GOOD, CRITICAL = "#0ca30c", "#d03b3b"
MUTED, GRID = "#898781", "#e1e0d9"
SENTIMENT_COLOR = {"긍정": GOOD, "중립": MUTED, "부정": CRITICAL}
SEQUENTIAL_BLUE = [[0, "#cde2fb"], [0.35, "#6da7ec"], [0.65, "#2a78d6"], [1, "#0d366b"]]

# 시/도 대표 좌표(중심점 근사치) — GeoJSON 없이 Scattergeo로 지도에 찍기 위한 용도
REGION_COORDS = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "경기": (37.4138, 127.5183), "강원": (37.8228, 128.1555),
    "충북": (36.6357, 127.4917), "충남": (36.5184, 126.8000), "전북": (35.7175, 127.1530),
    "전남": (34.8679, 126.9910), "경북": (36.4919, 128.8889), "경남": (35.4606, 128.2132),
    "제주": (33.4996, 126.5312),
}


@st.cache_data
def load_data():
    voc = pd.read_csv(f"{RAW}/ecommerce_voc_synthetic_1000.csv", encoding="utf-8-sig")
    voc["접수일시"] = pd.to_datetime(voc["접수일시"])
    voc["month"] = voc["접수일시"].dt.to_period("M").astype(str)

    cust = pd.read_csv(f"{RAW}/ecommerce_customers.csv", encoding="utf-8-sig")
    cust["join_date"] = pd.to_datetime(cust["join_date"])
    cust["가입월"] = cust["join_date"].dt.to_period("M").astype(str)

    cons = pd.read_csv(f"{RAW}/ecommerce_consultations.csv", encoding="utf-8-sig")
    cons["consult_date"] = pd.to_datetime(cons["consult_date"])
    cons["month"] = cons["consult_date"].dt.to_period("M").astype(str)

    sat = pd.read_csv(f"{RAW}/ecommerce_satisfaction.csv", encoding="utf-8-sig")
    sat["survey_date"] = pd.to_datetime(sat["survey_date"])

    usage = pd.read_csv(f"{RAW}/ecommerce_usage_history.csv", encoding="utf-8-sig")

    agents = pd.read_csv(f"{RAW}/ecommerce_agents.csv", encoding="utf-8-sig")
    agents["hire_date"] = pd.to_datetime(agents["hire_date"])
    agents["tenure_months"] = ((pd.Timestamp("2025-12-31") - agents["hire_date"]).dt.days / 30.44).round(1)
    per_agent = (
        cons.merge(sat[["consult_id", "csat"]], on="consult_id", how="left")
        .groupby("agent_id")
        .agg(csat_avg=("csat", "mean"), recontact_rate=("is_recontact", lambda s: (s == "Y").mean() * 100))
    )
    agents = agents.merge(per_agent, on="agent_id", how="left")

    merged = sat.merge(cons, on=["consult_id", "customer_id"], how="left").merge(cust, on="customer_id", how="left")
    return {"voc": voc, "cust": cust, "cons": cons, "sat": sat, "usage": usage, "merged": merged, "agents": agents}


def _layout(fig, title, show_legend=True):
    fig.update_layout(
        title=title,
        margin=dict(t=48, l=10, r=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#1c2733"),
        showlegend=show_legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=380,
    )
    fig.update_xaxes(gridcolor=GRID, showline=True, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, showline=False)
    return fig


def overall_churn_stats(cust):
    total = len(cust)
    churned = int((cust["churn_yn"] == "Y").sum())
    return {"total": total, "churned": churned, "rate": round(churned / total * 100, 1)}


# ---------------- VOC 현황 ----------------

def filter_voc(voc, date_range, categories, channels):
    df = voc[(voc["접수일시"].dt.date >= date_range[0]) & (voc["접수일시"].dt.date <= date_range[1])]
    if categories:
        df = df[df["대분류"].isin(categories)]
    if channels:
        df = df[df["채널"].isin(channels)]
    return df


def fig_voc_category(df):
    g = df.groupby("대분류").agg(전체=("voc_id", "count"), 부정=("감정분류", lambda s: (s == "부정").sum()))
    g = g.sort_values("전체", ascending=False)
    fig = go.Figure()
    fig.add_bar(x=g.index, y=g["전체"], name="전체 건수", marker_color=MUTED)
    fig.add_bar(x=g.index, y=g["부정"], name="부정 건수", marker_color=CRITICAL)
    fig.update_layout(barmode="group")
    return _layout(fig, "대분류별 전체·부정 VOC 건수")


def fig_voc_monthly(df):
    g = df.groupby("month").agg(전체=("voc_id", "count"), 부정=("감정분류", lambda s: (s == "부정").sum())).reset_index()
    fig = go.Figure()
    fig.add_scatter(x=g["month"], y=g["전체"], name="전체 건수", mode="lines+markers", line=dict(color=BLUE, width=2))
    fig.add_scatter(x=g["month"], y=g["부정"], name="부정 건수", mode="lines+markers", line=dict(color=CRITICAL, width=2))
    return _layout(fig, "월별 전체·부정 VOC 추이")


def fig_voc_channel_count(df):
    g = df["채널"].value_counts()
    fig = go.Figure(go.Bar(x=g.index, y=g.values, marker_color=BLUE))
    return _layout(fig, "채널별 VOC 건수", show_legend=False)


def fig_voc_channel_negrate(df):
    g = df.groupby("채널")["감정분류"].apply(lambda s: (s == "부정").mean() * 100).sort_values(ascending=False)
    fig = go.Figure(go.Bar(x=g.index, y=g.values.round(1), marker_color=CRITICAL))
    return _layout(fig, "채널별 부정 VOC 비율(%)", show_legend=False)


def fig_voc_sentiment_donut(df):
    g = df["감정분류"].value_counts()
    colors = [SENTIMENT_COLOR.get(k, MUTED) for k in g.index]
    fig = go.Figure(go.Pie(labels=g.index, values=g.values, hole=0.55, marker=dict(colors=colors)))
    return _layout(fig, "전체 감정분류 비율")


def fig_voc_churn_history(voc, cust):
    """해지관련(탈퇴 문의) 부정 VOC 이력 유무별 이탈율 — 이 데이터엔 '해지관련' 대분류가 따로 없어
    가장 가까운 소분류인 '탈퇴 문의'(회원/계정)로 대체했다."""
    flagged_ids = set(voc[(voc["소분류"] == "탈퇴 문의") & (voc["감정분류"] == "부정")]["고객ID"].dropna())
    has_history = cust["customer_id"].isin(flagged_ids)
    overall_rate = (cust["churn_yn"] == "Y").mean() * 100
    flagged_rate = (cust.loc[has_history, "churn_yn"] == "Y").mean() * 100 if has_history.any() else 0
    labels = ["전체 고객", "해지(탈퇴 문의) 부정 VOC 이력 있음"]
    values = [overall_rate, flagged_rate]
    colors = [MUTED, CRITICAL]
    fig = go.Figure(go.Bar(x=labels, y=[round(v, 1) for v in values], marker_color=colors,
                           text=[f"{v:.1f}%" for v in values], textposition="outside"))
    n = int(has_history.sum())
    return _layout(fig, f"해지관련 부정 VOC 이력 유무별 이탈율 (이력 있음 n={n})", show_legend=False)


def fig_voc_breakdown(df, category, sentiment="부정"):
    sub = df[df["대분류"] == category]
    if sentiment != "전체":
        sub = sub[sub["감정분류"] == sentiment]
    counts = sub["소분류"].value_counts().sort_values(ascending=True)
    color = SENTIMENT_COLOR.get(sentiment, BLUE)
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", marker_color=color,
                           text=counts.values, textposition="outside"))
    label = f"{category} · {sentiment} VOC 유형 분해 (전체 {len(sub)}건)"
    return _layout(fig, label, show_legend=False)


# ---------------- 만족도 (CSAT/NPS) ----------------

def filter_merged(merged, date_range, channels):
    df = merged[(merged["consult_date"].dt.date >= date_range[0]) & (merged["consult_date"].dt.date <= date_range[1])]
    if channels:
        df = df[df["channel"].isin(channels)]
    return df


def scorecard(df):
    csat_mean = round(float(df["csat"].mean()), 2) if len(df) else 0.0
    nps_mean = round(float(df["nps"].mean()), 2) if len(df) else 0.0
    promoter = float((df["nps"] >= 9).mean() * 100) if len(df) else 0.0
    detractor = float((df["nps"] <= 6).mean() * 100) if len(df) else 0.0
    nps_score = round(promoter - detractor, 1)
    low_ratio = round(float((df["csat"] <= 2).mean() * 100), 1) if len(df) else 0.0
    return {"csat_mean": csat_mean, "nps_mean": nps_mean, "nps_score": nps_score, "low_ratio": low_ratio, "n": len(df)}


def fig_csat_by_category(df):
    g = df.groupby("category")["csat"].mean().sort_values()
    overall = df["csat"].mean()
    fig = go.Figure(go.Bar(x=g.index, y=g.values.round(2), marker_color=BLUE))
    fig.add_hline(y=overall, line_dash="dash", line_color=CRITICAL,
                  annotation_text=f"전체 평균 {overall:.2f}", annotation_position="top left")
    return _layout(fig, "상담 카테고리별 CSAT 평균", show_legend=False)


def fig_csat_hist(df):
    fig = go.Figure(go.Histogram(x=df["csat"], xbins=dict(start=0.5, end=5.5, size=1), marker_color=BLUE))
    return _layout(fig, "CSAT 점수 분포", show_legend=False)


def fig_channel_csat(df):
    g = df.groupby("channel")["csat"].mean().sort_values()
    fig = go.Figure(go.Bar(x=g.index, y=g.values.round(2), marker_color=BLUE))
    return _layout(fig, "채널별 CSAT 평균", show_legend=False)


def drilldown_low_csat(df, category=None):
    sub = df[df["csat"] <= 2]
    if category:
        sub = sub[sub["category"] == category]
    cols = ["consult_date", "channel", "category", "csat", "nps", "comment"]
    return sub[cols].sort_values("consult_date", ascending=False)


def fig_channel_recontact(df):
    g = df.groupby("channel")["is_recontact"].apply(lambda s: (s == "Y").mean() * 100).sort_values(ascending=False)
    fig = go.Figure(go.Bar(x=g.index, y=g.values.round(1), marker_color=ORANGE))
    return _layout(fig, "채널별 재문의율(%)", show_legend=False)


def fig_channel_csat_recontact_combo(df):
    """교안이 명시적으로 요구하는 이중축(dual-axis) 결합차트 버전 —
    dataviz 원칙상 단일축 분리가 더 낫지만(위 두 함수), 이번 과제 요구사항 자체가 결합차트라 별도로 만든다."""
    csat = df.groupby("channel")["csat"].mean().sort_values()
    recontact = df.groupby("channel")["is_recontact"].apply(lambda s: (s == "Y").mean() * 100).reindex(csat.index)
    fig = go.Figure()
    fig.add_bar(x=csat.index, y=csat.values.round(2), name="CSAT 평균", marker_color=BLUE, yaxis="y")
    fig.add_scatter(x=recontact.index, y=recontact.values.round(1), name="재문의율(%)", mode="lines+markers",
                    line=dict(color=ORANGE, width=2), yaxis="y2")
    fig.update_layout(
        yaxis=dict(title="CSAT 평균", range=[0, 5]),
        yaxis2=dict(title="재문의율(%)", overlaying="y", side="right", range=[0, 40]),
    )
    return _layout(fig, "채널별 CSAT x 재문의율 (결합차트)")


# ---------------- 재문의 · 이탈 ----------------

def _chain_buckets(merged, date_range, channels):
    df = filter_merged(merged, date_range, channels)
    chain = df.groupby("customer_id")["is_recontact"].apply(lambda s: (s == "Y").sum())
    bucket = pd.cut(chain, bins=[-1, 0, 1, 99], labels=["재문의 없음", "재문의 1회", "재문의 2회+"])
    cust_rows = df.drop_duplicates("customer_id").set_index("customer_id")
    return bucket, cust_rows


def fig_chain(merged, date_range, channels):
    bucket, cust_rows = _chain_buckets(merged, date_range, channels)
    churn = cust_rows["churn_yn"].reindex(bucket.index)
    g = pd.DataFrame({"구간": bucket, "이탈": churn})
    rate = g.groupby("구간", observed=True)["이탈"].apply(lambda s: (s == "Y").mean() * 100)
    n = g.groupby("구간", observed=True).size()
    overall = (churn == "Y").mean() * 100
    colors = [CRITICAL if v == rate.max() else MUTED for v in rate.values]
    fig = go.Figure(go.Bar(x=rate.index.astype(str), y=rate.values.round(1), marker_color=colors,
                           text=[f"{v:.1f}% (n={n[i]})" for i, v in rate.items()], textposition="outside"))
    fig.add_hline(y=overall, line_dash="dash", line_color=BLUE, annotation_text=f"전체 평균 {overall:.1f}%")
    return _layout(fig, "재문의 횟수 구간별 이탈율", show_legend=False)


def drilldown_chain_customers(merged, date_range, channels, bucket_label):
    bucket, cust_rows = _chain_buckets(merged, date_range, channels)
    ids = bucket[bucket == bucket_label].index
    cols = ["name", "age", "gender", "region", "membership_grade", "churn_yn"]
    return cust_rows.loc[ids, cols].reset_index()


def filter_cons(cons, date_range, channels):
    df = cons[(cons["consult_date"].dt.date >= date_range[0]) & (cons["consult_date"].dt.date <= date_range[1])]
    if channels:
        df = df[df["channel"].isin(channels)]
    return df


def fig_recontact_monthly(cons, date_range, channels):
    df = filter_cons(cons, date_range, channels)
    g = df.groupby("month")["is_recontact"].apply(lambda s: (s == "Y").mean() * 100).reset_index()
    fig = go.Figure(go.Scatter(x=g["month"], y=g["is_recontact"].round(1), mode="lines+markers",
                                line=dict(color=ORANGE, width=2)))
    return _layout(fig, "월별 재문의율(%) 추이", show_legend=False)


# ---------------- 고객 현황 ----------------

def fig_grade_churn(cust):
    g = cust.groupby("membership_grade")["churn_yn"].apply(lambda s: (s == "Y").mean() * 100)
    order = ["VIP", "GOLD", "SILVER", "일반", "BRONZE"]
    g = g.reindex([o for o in order if o in g.index])
    fig = go.Figure(go.Bar(x=g.index, y=g.values.round(1), marker_color=BLUE))
    return _layout(fig, "회원등급별 이탈율(%)", show_legend=False)


def fig_region_churn(cust):
    counts = cust["region"].value_counts()
    g = cust.groupby("region")["churn_yn"].apply(lambda s: (s == "Y").mean() * 100).sort_values(ascending=False)
    colors = [BLUE if counts[r] >= 30 else MUTED for r in g.index]
    fig = go.Figure(go.Bar(x=g.index, y=g.values.round(1), marker_color=colors,
                           text=[f"n={counts[r]}" for r in g.index], textposition="outside"))
    return _layout(fig, "지역별 이탈율(%) — 진한 막대만 표본 30건 이상", show_legend=False)


def fig_region_map(cust):
    counts = cust["region"].value_counts()
    churned = cust.groupby("region")["churn_yn"].apply(lambda s: (s == "Y").sum())
    churn = cust.groupby("region")["churn_yn"].apply(lambda s: (s == "Y").mean() * 100)
    regions = [r for r in REGION_COORDS if r in counts.index]
    lats = [REGION_COORDS[r][0] for r in regions]
    lons = [REGION_COORDS[r][1] for r in regions]
    rates = [float(churn[r]) for r in regions]
    # 실제 이탈율 범위로 색상 스케일을 당겨써야 미세한 차이가 눈에 들어온다(0%~최댓값으로 두면 저채도 구간만 쓰임).
    cmin, cmax = min(rates), max(rates)
    sizes = [9 + (counts[r] ** 0.5) * 3 for r in regions]  # 면적 비례(sqrt) + 최소 가독 크기 확보
    # customdata에 지역명까지 담아둔다 — Streamlit의 클릭 선택 이벤트 스키마는 "text"를 보장하지 않고
    # customdata만 항상 포함하므로, 클릭 핸들러에서 필요한 값 전부를 여기서 꺼낼 수 있게 한다.
    customdata = [[r, int(counts[r]), int(churned[r]), round(churn[r], 1)] for r in regions]
    fig = go.Figure(go.Scattergeo(
        lat=lats, lon=lons, text=regions, customdata=customdata,
        mode="markers",
        hovertemplate="<b>%{customdata[0]}</b><br>고객수: %{customdata[1]}명<br>이탈 고객수: %{customdata[2]}명<br>이탈율: %{customdata[3]}%<extra></extra>",
        marker=dict(
            size=sizes, sizemode="diameter",
            color=rates, colorscale=SEQUENTIAL_BLUE, cmin=cmin, cmax=cmax,
            colorbar=dict(title="이탈율(%)"),
            line=dict(width=1.5, color="#0b0b0b"), opacity=0.85,
        ),
    ))
    fig.update_geos(
        scope="asia", lataxis_range=[32, 40], lonaxis_range=[123, 132],
        showcountries=True, countrycolor=GRID, showland=True, landcolor="#f9f9f7",
        showocean=True, oceancolor="#eef3f8", showlakes=False, resolution=50,
    )
    fig.update_layout(height=460)
    return _layout(fig, "지역별 고객수(버블 크기) x 이탈율(색상) — 클릭하면 아래에 상세 표시", show_legend=False)


def fig_join_cohort(cust):
    g = cust.groupby("가입월")["churn_yn"].apply(lambda s: (s == "Y").mean() * 100).reset_index()
    fig = go.Figure(go.Scatter(x=g["가입월"], y=g["churn_yn"].round(1), mode="lines+markers",
                                line=dict(color=VIOLET, width=2)))
    return _layout(fig, "가입월 코호트별 이탈율(%)", show_legend=False)


def fig_age_dist(cust):
    fig = go.Figure(go.Histogram(x=cust["age"], xbins=dict(size=5), marker_color=AQUA))
    return _layout(fig, "고객 연령 분포", show_legend=False)


def fig_tenure_usage_scatter(cust, usage, ref_date="2025-12-31"):
    tenure = ((pd.Timestamp(ref_date) - cust["join_date"]).dt.days / 30.44).round(1)
    avg_purchase = usage.groupby("customer_id")["purchase_amount"].mean()
    df = cust.assign(tenure_months=tenure).merge(
        avg_purchase.rename("avg_purchase"), on="customer_id", how="left"
    ).dropna(subset=["avg_purchase"])
    fig = go.Figure()
    for churn_val, color, name in [("N", BLUE, "유지"), ("Y", CRITICAL, "이탈")]:
        sub = df[df["churn_yn"] == churn_val]
        fig.add_scatter(
            x=sub["tenure_months"], y=sub["avg_purchase"], mode="markers", name=name,
            marker=dict(color=color, size=8, opacity=0.65),
            customdata=sub[["customer_id"]].values,
            hovertemplate="고객ID: %{customdata[0]}<br>가입기간: %{x}개월<br>월평균 구매금액: %{y:,.0f}원<extra>" + name + "</extra>",
        )
    fig.update_xaxes(title="가입기간(개월)")
    fig.update_yaxes(title="월평균 구매금액(원)")
    return _layout(fig, "가입기간 x 이용량(월평균 구매금액) 산점도")


# ---------------- 상담원 관점 (직원만족도·eNPS) — 3주차 Day2/3 ----------------

def filter_agents(agents, team):
    if team == "전체":
        return agents
    return agents[agents["team"] == team]


def _enps(df):
    if len(df) == 0:
        return 0.0
    promoter = (df["agent_satisfaction"] >= 9).mean() * 100
    detractor = (df["agent_satisfaction"] <= 6).mean() * 100
    return round(promoter - detractor, 1)


def fig_enps_gauge(df):
    value = _enps(df)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": f"eNPS (n={len(df)})"},
        gauge={
            "axis": {"range": [-100, 100]},
            "bar": {"color": "#1c2733"},
            "steps": [{"range": [-100, 0], "color": "#f6c6c6"}, {"range": [0, 100], "color": "#c8e6c9"}],
        },
    ))
    fig.update_layout(height=280, paper_bgcolor="rgba(0,0,0,0)", margin=dict(t=48, l=10, r=10, b=10))
    return fig


def _partial_corr(x, y, z):
    """z(근속기간)를 통제한 x-y 편상관계수. 교란변수 검증용(2026-07-22 추가)."""
    rxy, _ = stats.pearsonr(x, y)
    rxz, _ = stats.pearsonr(x, z)
    ryz, _ = stats.pearsonr(y, z)
    denom = ((1 - rxz ** 2) * (1 - ryz ** 2)) ** 0.5
    if denom == 0:
        return float("nan"), float("nan")
    r_partial = (rxy - rxz * ryz) / denom
    n = len(x)
    if n <= 3 or abs(r_partial) >= 1:
        return r_partial, float("nan")
    t = r_partial * ((n - 3) / (1 - r_partial ** 2)) ** 0.5
    p = 2 * (1 - stats.t.cdf(abs(t), df=n - 3))
    return r_partial, p


def fig_burnout_csat_scatter(df):
    """번아웃(초과근무) x CSAT 산점도 + 추세선. 표본이 작으면(<10) 상관계수를
    신뢰하기 어렵다는 경고를 텍스트에 그대로 표시한다(교안 Day3 "표본이 6명으로
    줄면 상관계수를 믿기 어렵다" 원칙). 점 색상은 근속기간(개월) — 근속기간이 짧을수록
    (신입일수록) 번아웃도 높고 만족도도 낮은 경향이 있어, 이 관계가 번아웃 자체보다
    근속기간(온보딩 시기) 때문일 수 있음을 편상관계수로 함께 표시한다(2026-07-22 확인)."""
    df = df.dropna(subset=["overtime_hours_avg", "csat_avg"])
    small_sample = len(df) < 10
    has_tenure = "tenure_months" in df.columns and df["tenure_months"].notna().all() and len(df) >= 4

    if len(df) >= 3:
        r, p = stats.pearsonr(df["overtime_hours_avg"], df["csat_avg"])
    else:
        r, p = float("nan"), float("nan")

    marker = dict(size=10, line=dict(width=1, color="#0d366b"))
    if has_tenure:
        marker.update(color=df["tenure_months"], colorscale="Blues_r", showscale=True,
                       colorbar=dict(title="근속(개월)"))
    else:
        marker["color"] = "#2a78d6"

    if small_sample or len(df) < 3:
        fig = px.scatter(
            df, x="overtime_hours_avg", y="csat_avg",
            hover_data=["agent_id"],
            labels={"overtime_hours_avg": "월 평균 초과근무시간", "csat_avg": "상담원별 CSAT 평균"},
        )
        note = f"표본 n={len(df)}명 — 너무 적어 상관계수는 참고용" if len(df) >= 3 else f"표본 n={len(df)}명 — 상관계수 계산 불가"
    else:
        fig = px.scatter(
            df, x="overtime_hours_avg", y="csat_avg", trendline="ols",
            hover_data=["agent_id"],
            labels={"overtime_hours_avg": "월 평균 초과근무시간", "csat_avg": "상담원별 CSAT 평균"},
        )
        fig.update_traces(line=dict(color="#eb6834", width=2), selector=dict(mode="lines"))
        sig = "p<0.05, 유의함" if p < 0.05 else "p≥0.05, 유의하지 않음"
        note = f"r = {r:.2f} ({sig})"
        if has_tenure:
            r_p, p_p = _partial_corr(df["overtime_hours_avg"], df["csat_avg"], df["tenure_months"])
            note += f"<br>근속기간 통제 후: r = {r_p:.2f} (p={p_p:.2f})"

    fig.update_traces(marker=marker, selector=dict(mode="markers"))
    fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.98, showarrow=False, text=note, align="right",
                        font=dict(size=13, color="#d03b3b" if small_sample else "#1c2733"))
    return _layout(fig, "번아웃(초과근무) x CSAT 산점도 + 추세선 (색=근속기간)", show_legend=False)


def fig_training_compare(df):
    g = df.groupby("training_completed_yn").agg(csat_avg=("csat_avg", "mean"), recontact_rate=("recontact_rate", "mean"))
    labels = {"Y": "이수", "N": "미이수"}
    colors = {"Y": "#2a78d6", "N": "#898781"}
    order = [k for k in ["Y", "N"] if k in g.index]

    from plotly.subplots import make_subplots
    fig = make_subplots(rows=1, cols=2, subplot_titles=("CSAT 평균", "재문의율(%)"))
    fig.add_bar(x=[labels[k] for k in order], y=[round(g.loc[k, "csat_avg"], 2) for k in order],
                marker_color=[colors[k] for k in order],
                text=[f"{g.loc[k, 'csat_avg']:.2f}" for k in order], textposition="outside",
                row=1, col=1, showlegend=False)
    fig.add_bar(x=[labels[k] for k in order], y=[round(g.loc[k, "recontact_rate"], 1) for k in order],
                marker_color=[colors[k] for k in order],
                text=[f"{g.loc[k, 'recontact_rate']:.1f}%" for k in order], textposition="outside",
                row=1, col=2, showlegend=False)
    fig.update_layout(title="교육 이수 여부(Y/N)별 CSAT·재문의율 비교",
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=360,
                       margin=dict(t=64, l=10, r=10, b=10))
    return fig


# ---------------- 근속기간(재직기간) 교란변수 분석 — 2026-07-22 추가 ----------------

def tenure_corr_table(df):
    """근속기간과 주요 지표의 상관관계 요약표. 리포트 텍스트로만 있던 표를
    실제 데이터 표(st.dataframe)로 만든다."""
    sub = df.dropna(subset=["tenure_months"])
    rows = []
    for col, label in [
        ("agent_satisfaction", "직원만족도"), ("overtime_hours_avg", "초과근무시간"),
        ("qa_score", "QA(품질)점수"), ("csat_avg", "상담원별 CSAT"), ("recontact_rate", "상담원별 재문의율"),
    ]:
        d = sub.dropna(subset=[col])
        if len(d) >= 3:
            r, p = stats.pearsonr(d["tenure_months"], d[col])
            rows.append({"지표": label, "r": round(float(r), 3), "p": round(float(p), 4),
                         "유의성(α=.05)": "유의함" if p < 0.05 else "유의하지 않음", "n": len(d)})
        else:
            rows.append({"지표": label, "r": None, "p": None, "유의성(α=.05)": "표본 부족", "n": len(d)})

    for bin_col, label in [("training_completed_yn", "교육이수여부(Y=1)"), ("turnover_yn", "이직여부(Y=1)")]:
        d2 = sub.dropna(subset=[bin_col])
        if len(d2) >= 3 and d2[bin_col].nunique() == 2:
            y = (d2[bin_col] == "Y").astype(int)
            r, p = stats.pointbiserialr(y, d2["tenure_months"])
            rows.append({"지표": label, "r": round(float(r), 3), "p": round(float(p), 4),
                         "유의성(α=.05)": "유의함" if p < 0.05 else "유의하지 않음", "n": len(d2)})
    return pd.DataFrame(rows)


def fig_tenure_satisfaction(df):
    sub = df.dropna(subset=["tenure_months", "agent_satisfaction"])
    fig = px.scatter(
        sub, x="tenure_months", y="agent_satisfaction",
        trendline="ols" if len(sub) >= 3 else None, hover_data=["agent_id"],
        labels={"tenure_months": "근속기간(개월)", "agent_satisfaction": "직원만족도(0~10)"},
    )
    fig.update_traces(marker=dict(size=10, color="#2a78d6", line=dict(width=1, color="#0d366b")), selector=dict(mode="markers"))
    fig.update_traces(line=dict(color="#eb6834", width=2), selector=dict(mode="lines"))
    note = "표본 부족"
    if len(sub) >= 3:
        r, p = stats.pearsonr(sub["tenure_months"], sub["agent_satisfaction"])
        note = f"r = {r:.2f} ({'p<0.05, 유의함' if p < 0.05 else 'p≥0.05, 유의하지 않음'})"
    fig.add_annotation(xref="paper", yref="paper", x=0.02, y=0.98, showarrow=False, text=note,
                        font=dict(size=13, color="#1c2733"), align="left")
    return _layout(fig, "근속기간 x 직원만족도", show_legend=False)


def fig_tenure_overtime(df):
    sub = df.dropna(subset=["tenure_months", "overtime_hours_avg"])
    fig = px.scatter(
        sub, x="tenure_months", y="overtime_hours_avg",
        trendline="ols" if len(sub) >= 3 else None, hover_data=["agent_id"],
        labels={"tenure_months": "근속기간(개월)", "overtime_hours_avg": "월 평균 초과근무시간"},
    )
    fig.update_traces(marker=dict(size=10, color="#eb6834", line=dict(width=1, color="#8a3f14")), selector=dict(mode="markers"))
    fig.update_traces(line=dict(color="#4a3aa7", width=2), selector=dict(mode="lines"))
    note = "표본 부족"
    if len(sub) >= 3:
        r, p = stats.pearsonr(sub["tenure_months"], sub["overtime_hours_avg"])
        note = f"r = {r:.2f} ({'p<0.05, 유의함' if p < 0.05 else 'p≥0.05, 유의하지 않음'})"
    fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.98, showarrow=False, text=note,
                        font=dict(size=13, color="#1c2733"), align="right")
    return _layout(fig, "근속기간 x 초과근무시간", show_legend=False)


def fig_tenure_by_training(df):
    """교육 이수(Y) vs 미이수(N) 그룹의 근속기간 분포 — 두 그룹이 근속기간으로
    거의 완벽히 갈린다는 것을 박스플롯 + 개별 점으로 직접 보여준다."""
    sub = df.dropna(subset=["tenure_months", "training_completed_yn"])
    labels = {"Y": "이수", "N": "미이수"}
    colors = {"Y": "#2a78d6", "N": "#898781"}
    fig = go.Figure()
    for k in ["Y", "N"]:
        g = sub[sub["training_completed_yn"] == k]
        if len(g) == 0:
            continue
        fig.add_trace(go.Box(
            y=g["tenure_months"], name=labels[k], marker_color=colors[k],
            boxpoints="all", jitter=0.4, pointpos=0,
            hovertext=g["agent_id"], hoverinfo="y+text",
        ))
    fig.update_layout(yaxis_title="근속기간(개월)")
    return _layout(fig, "교육 이수 여부별 근속기간 분포 (점 하나 = 상담원 1명)", show_legend=False)


def fig_tenure_by_turnover(df):
    """이직 여부(Y/N)별 근속기간 분포. 이번 3주차 분석에서 가장 통계적으로
    확실한 발견(point-biserial r=-0.60, p=0.005) — 이직자 전원이 근속
    24개월 미만에 몰려 있다는 것을 점으로 직접 보여준다(2026-07-22 추가)."""
    sub = df.dropna(subset=["tenure_months", "turnover_yn"])
    labels = {"N": "재직중", "Y": "이직"}
    colors = {"N": "#2a78d6", "Y": "#d03b3b"}
    fig = go.Figure()
    for k in ["N", "Y"]:
        g = sub[sub["turnover_yn"] == k]
        if len(g) == 0:
            continue
        fig.add_trace(go.Box(
            y=g["tenure_months"], name=labels[k], marker_color=colors[k],
            boxpoints="all", jitter=0.4, pointpos=0,
            hovertext=g["agent_id"], hoverinfo="y+text",
        ))
    note = "표본 부족"
    y_train = sub["turnover_yn"]
    if len(sub) >= 3 and y_train.nunique() == 2:
        y = (y_train == "Y").astype(int)
        r, p = stats.pointbiserialr(y, sub["tenure_months"])
        sig = "p<0.05, 유의함" if p < 0.05 else "p≥0.05, 유의하지 않음"
        note = f"r = {r:.2f} ({sig})"
    fig.add_annotation(xref="paper", yref="paper", x=0.98, y=0.98, showarrow=False, text=note,
                        font=dict(size=13, color="#1c2733"), align="right")
    fig.update_layout(yaxis_title="근속기간(개월)")
    return _layout(fig, "이직 여부별 근속기간 분포 (점 하나 = 상담원 1명)", show_legend=False)


def fig_confound_comparison(df):
    """원래 상관계수 vs 근속기간을 통제한 편상관계수를 나란히 비교 — '착시가
    사라진다'는 것을 표가 아니라 막대그래프로 직접 보여준다."""
    pairs = [
        ("overtime_hours_avg", "csat_avg", "번아웃 ↔ CSAT"),
        ("agent_satisfaction", "recontact_rate", "만족도 ↔ 재문의율"),
    ]
    labels, raw_r, partial_r = [], [], []
    for x_col, y_col, label in pairs:
        sub = df.dropna(subset=[x_col, y_col, "tenure_months"])
        if len(sub) < 4:
            continue
        r, _ = stats.pearsonr(sub[x_col], sub[y_col])
        r_p, _ = _partial_corr(sub[x_col], sub[y_col], sub["tenure_months"])
        labels.append(label)
        raw_r.append(round(float(r), 2))
        partial_r.append(round(float(r_p), 2))

    fig = go.Figure()
    fig.add_bar(x=labels, y=raw_r, name="원래 r", marker_color="#d03b3b")
    fig.add_bar(x=labels, y=partial_r, name="근속기간 통제 후 r", marker_color="#898781")
    fig.update_layout(barmode="group", yaxis_title="상관계수 r", yaxis=dict(range=[-1, 1]))
    fig.add_hline(y=0, line_color="#607080", line_width=1)
    return _layout(fig, "근속기간 통제 전후 상관계수 비교", show_legend=True)


def drilldown_customers(cust, grades, regions):
    df = cust
    if grades:
        df = df[df["membership_grade"].isin(grades)]
    if regions:
        df = df[df["region"].isin(regions)]
    cols = ["customer_id", "name", "age", "gender", "region", "membership_grade", "join_date", "churn_yn"]
    return df[cols].sort_values("join_date", ascending=False)
