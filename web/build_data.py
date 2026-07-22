# -*- coding: utf-8 -*-
"""정적 HTML 대시보드(Cloudflare/Netlify)용 데이터 빌드 스크립트.
Cloudflare Pages/Netlify는 정적 파일만 서빙하므로 Python이 서버에서 돌지 않는다 —
그래서 배포 '빌드 시점'에 이 스크립트를 실행해 web/data.json을 미리 구워두고,
index.html은 fetch("data.json")로 원자료(raw rows)를 읽어 브라우저에서 직접
기간/카테고리/채널로 필터링·집계한 뒤 Plotly.js로 그린다(Streamlit처럼 서버 재계산은
아니지만, 클라이언트에서 즉시 재계산되므로 필터 조작에는 실시간으로 반응한다).
raw/ CSV가 바뀌면 이 스크립트를 다시 실행해 data.json을 갱신해야 한다.
"""
import json
import re

import numpy as np
import pandas as pd
from scipy import stats

try:
    import markdown as md
except ImportError:
    md = None

BASE = "../raw"

voc = pd.read_csv(f"{BASE}/ecommerce_voc_synthetic_1000.csv", encoding="utf-8-sig")
voc["접수일시"] = pd.to_datetime(voc["접수일시"])

cons = pd.read_csv(f"{BASE}/ecommerce_consultations.csv", encoding="utf-8-sig")
cons["consult_date"] = pd.to_datetime(cons["consult_date"])

sat = pd.read_csv(f"{BASE}/ecommerce_satisfaction.csv", encoding="utf-8-sig")
cust = pd.read_csv(f"{BASE}/ecommerce_customers.csv", encoding="utf-8-sig")
usage = pd.read_csv(f"{BASE}/ecommerce_usage_history.csv", encoding="utf-8-sig")
merged = sat.merge(cons, on=["consult_id", "customer_id"], how="left").merge(cust, on="customer_id", how="left")
avg_purchase = usage.groupby("customer_id")["purchase_amount"].mean()

voc_rows = [
    {
        "date": row["접수일시"].strftime("%Y-%m-%d"),
        "channel": row["채널"],
        "cat": row["대분류"],
        "sub": row["소분류"],
        "sentiment": row["감정분류"],
        "text": row["문의내용"],
        "csat": None if pd.isna(row["만족도점수(CSAT)"]) else float(row["만족도점수(CSAT)"]),
        "customer_id": row["고객ID"],
    }
    for _, row in voc.iterrows()
]

merged_rows = [
    {
        "date": row["consult_date"].strftime("%Y-%m-%d"),
        "channel": row["channel"],
        "category": row["category"],
        "csat": float(row["csat"]),
        "nps": float(row["nps"]),
        "comment": None if pd.isna(row["comment"]) else row["comment"],
        "recontact": row["is_recontact"],
        "customer_id": row["customer_id"],
        "grade": row["membership_grade"],
        "region": row["region"],
        "churn": row["churn_yn"],
    }
    for _, row in merged.iterrows()
]

cust_rows = [
    {
        "customer_id": row["customer_id"], "name": row["name"], "age": int(row["age"]),
        "gender": row["gender"], "region": row["region"], "grade": row["membership_grade"],
        "join_date": row["join_date"], "churn": row["churn_yn"],
        "avg_purchase": None if row["customer_id"] not in avg_purchase.index or pd.isna(avg_purchase[row["customer_id"]])
                        else round(float(avg_purchase[row["customer_id"]]), 0),
    }
    for _, row in cust.iterrows()
]

overall = {"total": int(len(cust)), "churned": int((cust["churn_yn"] == "Y").sum())}
overall["rate"] = round(overall["churned"] / overall["total"] * 100, 1)

# ---------------- 상담원 관점 (3주차) ----------------
# r/p-value/추세선 계수는 팀 필터(전체/1팀/2팀/3팀) 4가지 경우의 수뿐이므로,
# 브라우저에서 통계 계산을 다시 구현하지 않고 빌드 시점에 전부 미리 구워둔다
# (Streamlit 버전과 정확히 같은 숫자를 보장하기 위함).
agents = pd.read_csv(f"{BASE}/ecommerce_agents.csv", encoding="utf-8-sig")
agents["hire_date"] = pd.to_datetime(agents["hire_date"])
agents["tenure_months"] = ((pd.Timestamp("2025-12-31") - agents["hire_date"]).dt.days / 30.44).round(1)
per_agent = (
    cons.merge(sat[["consult_id", "csat"]], on="consult_id", how="left")
    .groupby("agent_id")
    .agg(csat_avg=("csat", "mean"), recontact_rate=("is_recontact", lambda s: (s == "Y").mean() * 100))
)
agents = agents.merge(per_agent, on="agent_id", how="left")


def _enps(df):
    if len(df) == 0:
        return 0.0
    promoter = (df["agent_satisfaction"] >= 9).mean() * 100
    detractor = (df["agent_satisfaction"] <= 6).mean() * 100
    return round(promoter - detractor, 1)


def _partial_corr(x, y, z):
    rxy, _ = stats.pearsonr(x, y)
    rxz, _ = stats.pearsonr(x, z)
    ryz, _ = stats.pearsonr(y, z)
    denom = ((1 - rxz ** 2) * (1 - ryz ** 2)) ** 0.5
    if denom == 0:
        return None, None
    r_p = (rxy - rxz * ryz) / denom
    n = len(x)
    if n <= 3 or abs(r_p) >= 1:
        return round(float(r_p), 3), None
    t = r_p * ((n - 3) / (1 - r_p ** 2)) ** 0.5
    p_p = 2 * (1 - stats.t.cdf(abs(t), df=n - 3))
    return round(float(r_p), 3), round(float(p_p), 4)


def _linreg_points(sub, x_col, y_col):
    """산점도용 원자료 + OLS 추세선 계수 + r/p. n<3이면 추세선 없이 점만."""
    n = len(sub)
    r = p = slope = intercept = None
    if n >= 3:
        r, p = stats.pearsonr(sub[x_col], sub[y_col])
        slope, intercept = np.polyfit(sub[x_col], sub[y_col], 1)
        r, p, slope, intercept = round(float(r), 3), round(float(p), 4), float(slope), float(intercept)
    points = [{"agent_id": row["agent_id"], "x": float(row[x_col]), "y": float(row[y_col])} for _, row in sub.iterrows()]
    return {"n": n, "r": r, "p": p, "slope": slope, "intercept": intercept, "points": points}


def _corr_table(df):
    """근속기간과 주요 지표의 상관관계 요약표(리포트의 텍스트 표를 데이터로도 제공)."""
    sub = df.dropna(subset=["tenure_months"])
    rows = []
    for col, label in [
        ("agent_satisfaction", "직원만족도"), ("overtime_hours_avg", "초과근무시간"),
        ("csat_avg", "상담원별 CSAT"), ("recontact_rate", "상담원별 재문의율"),
    ]:
        d = sub.dropna(subset=[col])
        if len(d) >= 3:
            r, p = stats.pearsonr(d["tenure_months"], d[col])
            rows.append({"지표": label, "r": round(float(r), 3), "p": round(float(p), 4),
                         "유의성": "유의함" if p < 0.05 else "유의하지 않음", "n": len(d)})
        else:
            rows.append({"지표": label, "r": None, "p": None, "유의성": "표본 부족", "n": len(d)})
    d2 = sub.dropna(subset=["training_completed_yn"])
    if len(d2) >= 3:
        y = (d2["training_completed_yn"] == "Y").astype(int)
        r, p = stats.pointbiserialr(y, d2["tenure_months"])
        rows.append({"지표": "교육이수여부(Y=1)", "r": round(float(r), 3), "p": round(float(p), 4),
                     "유의성": "유의함" if p < 0.05 else "유의하지 않음", "n": len(d2)})
    return rows


def _team_block(df):
    scatter_df = df.dropna(subset=["overtime_hours_avg", "csat_avg"])
    n = len(scatter_df)
    r = p = slope = intercept = r_partial = p_partial = None
    if n >= 3:
        r, p = stats.pearsonr(scatter_df["overtime_hours_avg"], scatter_df["csat_avg"])
        slope, intercept = np.polyfit(scatter_df["overtime_hours_avg"], scatter_df["csat_avg"], 1)
        r, p, slope, intercept = round(float(r), 3), round(float(p), 4), float(slope), float(intercept)
    if n >= 4:
        r_partial, p_partial = _partial_corr(
            scatter_df["overtime_hours_avg"], scatter_df["csat_avg"], scatter_df["tenure_months"]
        )

    training = {}
    for k in ["Y", "N"]:
        sub = df[df["training_completed_yn"] == k]
        if len(sub):
            training[k] = {
                "csat_avg": round(float(sub["csat_avg"].mean()), 2),
                "recontact_rate": round(float(sub["recontact_rate"].mean()), 1),
            }

    points = [
        {"agent_id": row["agent_id"], "x": float(row["overtime_hours_avg"]), "y": float(row["csat_avg"]),
         "tenure": float(row["tenure_months"])}
        for _, row in scatter_df.iterrows()
    ]

    # 근속기간 관련 신규 시각화용 데이터
    tenure_satisfaction = _linreg_points(df.dropna(subset=["tenure_months", "agent_satisfaction"]), "tenure_months", "agent_satisfaction")
    tenure_overtime = _linreg_points(df.dropna(subset=["tenure_months", "overtime_hours_avg"]), "tenure_months", "overtime_hours_avg")
    training_tenure_points = [
        {"agent_id": row["agent_id"], "tenure": float(row["tenure_months"]), "training": row["training_completed_yn"]}
        for _, row in df.dropna(subset=["tenure_months", "training_completed_yn"]).iterrows()
    ]

    confound = []
    sat_recontact_df = df.dropna(subset=["agent_satisfaction", "recontact_rate", "tenure_months"])
    for x_col, y_col, label in [
        ("overtime_hours_avg", "csat_avg", "번아웃 ↔ CSAT"),
        ("agent_satisfaction", "recontact_rate", "만족도 ↔ 재문의율"),
    ]:
        sub2 = df.dropna(subset=[x_col, y_col, "tenure_months"])
        if len(sub2) < 4:
            continue
        raw_r, _ = stats.pearsonr(sub2[x_col], sub2[y_col])
        part_r, _ = _partial_corr(sub2[x_col], sub2[y_col], sub2["tenure_months"])
        confound.append({"label": label, "raw_r": round(float(raw_r), 2), "partial_r": round(float(part_r), 2)})

    return {
        "n": len(df), "enps": _enps(df), "r": r, "p": p, "slope": slope, "intercept": intercept,
        "r_partial": r_partial, "p_partial": p_partial,
        "points": points, "training": training,
        "tenure_satisfaction": tenure_satisfaction, "tenure_overtime": tenure_overtime,
        "training_tenure_points": training_tenure_points, "confound": confound,
        "corr_table": _corr_table(df),
    }


team_enps_all = {t: _enps(agents[agents["team"] == t]) for t in ["1팀", "2팀", "3팀"]}
agents_by_team = {"전체": _team_block(agents)}
for t in ["1팀", "2팀", "3팀"]:
    agents_by_team[t] = _team_block(agents[agents["team"] == t])
agents_by_team["전체"]["team_enps"] = team_enps_all

# ---------------- 개선 제안 리포트 (Day4) — 마크다운을 빌드 시점에 HTML로 변환 ----------------
report_html = ""
try:
    with open("../report/고객서비스_만족도개선_리포트.md", encoding="utf-8") as f:
        report_md = f.read()
    # 위키 내부 링크([[wiki/insights/...]])는 웹에서 열람 불가능한 로컬 경로이므로,
    # 링크가 아니라 마지막 경로 조각만 굵게 남긴 일반 텍스트로 바꾼다.
    report_md = re.sub(r"\[\[([^\]]+)\]\]", lambda m: f"**{m.group(1).split('/')[-1]}**", report_md)
    if md:
        report_html = md.markdown(report_md, extensions=["tables"])
    else:
        report_html = "<pre>" + report_md.replace("<", "&lt;") + "</pre>"
except FileNotFoundError:
    report_html = "<p>리포트 파일을 찾을 수 없습니다.</p>"

data = {
    "voc": voc_rows, "merged": merged_rows, "cust": cust_rows, "overall": overall,
    "agents_by_team": agents_by_team, "report_html": report_html,
}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

print(f"saved web/data.json (voc={len(voc_rows)}, merged={len(merged_rows)}, cust={len(cust_rows)}, "
      f"agents={agents_by_team['전체']['n']}, report_html={len(report_html)}자)")
