# -*- coding: utf-8 -*-
"""필터(기간·카테고리·채널)에 따라 즉시 재계산되는 Plotly 차트 모음.
기존 components/*.py(정적 PNG 생성)와 달리, 여기 함수들은 필터링된 DataFrame을 받아
매 요청마다 새로 그린다 — Streamlit이 요청마다 스크립트를 재실행하는 구조이기 때문에 가능하다.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

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

    merged = sat.merge(cons, on=["consult_id", "customer_id"], how="left").merge(cust, on="customer_id", how="left")
    return {"voc": voc, "cust": cust, "cons": cons, "sat": sat, "usage": usage, "merged": merged}


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


def drilldown_customers(cust, grades, regions):
    df = cust
    if grades:
        df = df[df["membership_grade"].isin(grades)]
    if regions:
        df = df[df["region"].isin(regions)]
    cols = ["customer_id", "name", "age", "gender", "region", "membership_grade", "join_date", "churn_yn"]
    return df[cols].sort_values("join_date", ascending=False)
