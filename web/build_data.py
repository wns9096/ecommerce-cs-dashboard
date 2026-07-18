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
import pandas as pd

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

data = {"voc": voc_rows, "merged": merged_rows, "cust": cust_rows, "overall": overall}

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

print(f"saved web/data.json (voc={len(voc_rows)}, merged={len(merged_rows)}, cust={len(cust_rows)})")
