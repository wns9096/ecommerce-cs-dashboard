# -*- coding: utf-8 -*-
"""컴포넌트③ 카테고리별 CSAT 진단: 낮은 순 정렬 + 전체평균 기준선 + 최저 2개 강조 + 건수 라벨."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

cons = pd.read_csv("raw/ecommerce_consultations.csv", encoding="utf-8-sig")
sat = pd.read_csv("raw/ecommerce_satisfaction.csv", encoding="utf-8-sig")
df = sat.merge(cons, on=["consult_id", "customer_id"], how="left")

g = df.groupby("category").agg(건수=("csat", "count"), CSAT평균=("csat", "mean")).sort_values("CSAT평균")
overall = df["csat"].mean()

colors = ["#e53935" if i < 2 else "#90a4ae" for i in range(len(g))]

fig, ax = plt.subplots(figsize=(9, 6))
bars = ax.bar(g.index, g["CSAT평균"], color=colors)
ax.axhline(overall, color="#e53935", linestyle="--", linewidth=1.5, label=f"전체 평균 {overall:.2f}")
for bar, cnt in zip(bars, g["건수"]):
    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02, f"n={cnt}", ha="center", fontsize=8, color="#546e7a")

ax.set_title("상담 카테고리별 CSAT 평균 (낮은 순)")
ax.set_ylabel("CSAT 평균")
ax.set_ylim(0, max(g["CSAT평균"]) + 0.5)
ax.legend()
plt.xticks(rotation=20, ha="right")
plt.tight_layout()
plt.savefig("components/output/03_카테고리별_저만족도.png", dpi=120)
print("saved")
