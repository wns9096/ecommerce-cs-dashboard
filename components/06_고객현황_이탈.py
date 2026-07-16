# -*- coding: utf-8 -*-
"""컴포넌트⑥ 고객 현황: 회원등급별·지역별 이탈율 2패널 + 전체평균 기준선."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

cust = pd.read_csv("raw/ecommerce_customers.csv", encoding="utf-8-sig")
overall = (cust["churn_yn"] == "Y").mean() * 100

grade_order = ["VIP", "GOLD", "SILVER", "BRONZE", "일반"]
g = cust.groupby("membership_grade").agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
g["이탈율"] = g["이탈수"] / g["고객수"] * 100
g = g.reindex(grade_order)

r = cust.groupby("region").agg(고객수=("customer_id", "count"), 이탈수=("churn_yn", lambda s: (s == "Y").sum()))
r["이탈율"] = r["이탈수"] / r["고객수"] * 100
r = r.sort_values("이탈율", ascending=False)

fig, axes = plt.subplots(1, 2, figsize=(15, 6))

ax = axes[0]
ax.bar(g.index, g["이탈율"], color="#1e88e5")
ax.axhline(overall, color="#e53935", linestyle="--", label=f"전체 평균 {overall:.1f}%")
ax.set_title("회원등급별 이탈율")
ax.set_ylabel("이탈율 (%)")
ax.legend()

ax2 = axes[1]
bar_colors = ["#90a4ae" if n < 30 else "#1e88e5" for n in r["고객수"]]
ax2.bar(r.index, r["이탈율"], color=bar_colors)
ax2.axhline(overall, color="#e53935", linestyle="--", label=f"전체 평균 {overall:.1f}%")
ax2.set_title("지역별 이탈율 (회색=표본 30건 미만 — 제주 외 전 지역 해당, 참고용)")
ax2.set_ylabel("이탈율 (%)")
plt.setp(ax2.get_xticklabels(), rotation=45, ha="right")
ax2.legend()

plt.tight_layout()
plt.savefig("components/output/06_고객현황_이탈.png", dpi=120)
print("saved")
