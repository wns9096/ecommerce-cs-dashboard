# -*- coding: utf-8 -*-
"""정적 HTML 대시보드(Cloudflare/Netlify)용 데이터 빌드 스크립트.
Cloudflare Pages/Netlify는 정적 파일만 서빙하므로 Python이 서버에서 돌지 않는다 —
그래서 배포 '빌드 시점'에 이 스크립트를 실행해 web/data.json을 미리 구워두고,
index.html은 fetch("data.json")로 이 결과만 읽어 Plotly.js로 그린다.
raw/ CSV가 바뀌면 이 스크립트를 다시 실행해 data.json을 갱신해야 한다(Streamlit처럼
매 요청마다 자동 재계산되지 않음 — 이것이 정적 호스팅과 서버 앱의 핵심 차이).
"""
import json
import pandas as pd

BASE = "../raw"

voc = pd.read_csv(f"{BASE}/ecommerce_voc_synthetic_1000.csv", encoding="utf-8-sig")
voc["접수일시"] = pd.to_datetime(voc["접수일시"])
voc["month"] = voc["접수일시"].dt.to_period("M").astype(str)

cons = pd.read_csv(f"{BASE}/ecommerce_consultations.csv", encoding="utf-8-sig")
sat = pd.read_csv(f"{BASE}/ecommerce_satisfaction.csv", encoding="utf-8-sig")
cust = pd.read_csv(f"{BASE}/ecommerce_customers.csv", encoding="utf-8-sig")
merged = sat.merge(cons, on=["consult_id", "customer_id"], how="left")

data = {}

# 1. VOC 현황
cat = voc.groupby("대분류").agg(전체=("voc_id", "count"), 부정=("감정분류", lambda s: (s == "부정").sum()))
cat = cat.sort_values("전체", ascending=False)
data["voc_category"] = {"labels": cat.index.tolist(), "전체": cat["전체"].tolist(), "부정": cat["부정"].tolist()}

mon = voc.groupby("month").agg(전체=("voc_id", "count"), 부정=("감정분류", lambda s: (s == "부정").sum()))
data["voc_monthly"] = {"labels": mon.index.tolist(), "전체": mon["전체"].tolist(), "부정": mon["부정"].tolist()}

worst = voc[(voc["대분류"] == "결제/환불") & (voc["감정분류"] == "부정")]
wc = worst["소분류"].value_counts().sort_values()
data["voc_worst_breakdown"] = {"labels": wc.index.tolist(), "values": wc.values.tolist()}

# 2. 만족도
csat_mean = float(sat["csat"].mean())
nps_mean = float(sat["nps"].mean())
promoter = float((sat["nps"] >= 9).mean() * 100)
detractor = float((sat["nps"] <= 6).mean() * 100)
nps_score = promoter - detractor
low_ratio = float((sat["csat"] <= 2).mean() * 100)
data["scorecard"] = {
    "csat_mean": round(csat_mean, 2), "nps_mean": round(nps_mean, 2),
    "nps_score": round(nps_score, 1), "low_ratio": round(low_ratio, 1), "n": int(len(sat)),
}

cat_csat = merged.groupby("category")["csat"].mean().sort_values()
data["csat_by_category"] = {"labels": cat_csat.index.tolist(), "values": [round(v, 2) for v in cat_csat.values], "overall": round(float(merged["csat"].mean()), 2)}

chan_csat = merged.groupby("channel")["csat"].mean().sort_values()
chan_recontact = cons.groupby("channel")["is_recontact"].apply(lambda s: (s == "Y").mean() * 100).reindex(chan_csat.index)
data["channel_combo"] = {"labels": chan_csat.index.tolist(), "csat": [round(v, 2) for v in chan_csat.values], "recontact": [round(v, 1) for v in chan_recontact.values]}

# 3. 재문의·이탈 체인
recontact_count = cons.groupby("customer_id")["is_recontact"].apply(lambda s: (s == "Y").sum())
churn = cust.set_index("customer_id")["churn_yn"].reindex(recontact_count.index).fillna("N")
churn_flag = churn == "Y"


def bucket(n):
    return "재문의 없음" if n == 0 else ("재문의 1회" if n == 1 else "재문의 2회+")


buckets = recontact_count.apply(bucket)
chain = pd.DataFrame({"bucket": buckets, "churn": churn_flag}).groupby("bucket")["churn"].agg(["mean", "count"]).reindex(["재문의 없음", "재문의 1회", "재문의 2회+"])
data["chain"] = {"labels": chain.index.tolist(), "이탈율": [round(v * 100, 1) for v in chain["mean"].values], "건수": chain["count"].tolist(), "overall": round(float(churn_flag.mean() * 100), 1)}

# 4. 고객 현황
grade_order = ["VIP", "GOLD", "SILVER", "BRONZE", "일반"]
g = cust.groupby("membership_grade")["churn_yn"].apply(lambda s: (s == "Y").mean() * 100).reindex(grade_order)
data["grade_churn"] = {"labels": grade_order, "values": [round(v, 1) for v in g.values], "overall": round(float((cust["churn_yn"] == "Y").mean() * 100), 1)}

r = cust.groupby("region").agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
r["이탈율"] = r["이탈수"] / r["고객수"] * 100
r = r.sort_values("이탈율", ascending=False)
data["region_churn"] = {"labels": r.index.tolist(), "values": [round(v, 1) for v in r["이탈율"].values], "counts": r["고객수"].tolist()}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("saved web/data.json")
