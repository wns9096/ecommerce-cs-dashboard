# -*- coding: utf-8 -*-
"""컴포넌트⑤ 상담→재문의→이탈 체인: 재문의 횟수 구간별(없음/1회/2회+) 이탈율 막대 + 전체평균 기준선."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

cons = pd.read_csv("raw/ecommerce_consultations.csv", encoding="utf-8-sig")
cust = pd.read_csv("raw/ecommerce_customers.csv", encoding="utf-8-sig")

recontact_count = cons.groupby("customer_id")["is_recontact"].apply(lambda s: (s == "Y").sum())
churn = cust.set_index("customer_id")["churn_yn"].reindex(recontact_count.index).fillna("N")
churn_flag = (churn == "Y")

def bucket(n):
    if n == 0:
        return "재문의 없음"
    elif n == 1:
        return "재문의 1회"
    else:
        return "재문의 2회+"

buckets = recontact_count.apply(bucket)
g = pd.DataFrame({"bucket": buckets, "churn": churn_flag}).groupby("bucket")["churn"].agg(["mean", "count"])
g["mean"] = g["mean"] * 100
order = ["재문의 없음", "재문의 1회", "재문의 2회+"]
g = g.reindex(order)
overall = churn_flag.mean() * 100

fig, ax = plt.subplots(figsize=(8, 6))
max_idx = g["mean"].idxmax()
colors = ["#e53935" if idx == max_idx else "#90a4ae" for idx in g.index]
bars = ax.bar(g.index, g["mean"], color=colors)
ax.axhline(overall, color="#1e88e5", linestyle="--", label=f"전체 평균 이탈율 {overall:.1f}%")
for bar, (idx, row) in zip(bars, g.iterrows()):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3, f"{row['mean']:.1f}% (n={int(row['count'])})", ha="center", fontsize=10)

ax.set_title("재문의 횟수 구간별 이탈율 (상담→재문의→이탈 체인)")
ax.set_ylabel("이탈율 (%)")
ax.legend()
plt.tight_layout()
plt.savefig("components/output/05_상담_재문의_이탈_체인.png", dpi=120)
print("saved")
print(g)
print(f"전체 평균: {overall:.1f}%")
