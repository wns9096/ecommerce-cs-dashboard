# -*- coding: utf-8 -*-
"""컴포넌트④ 채널별 CSAT x 재문의율 결합차트(dual-axis): 막대=CSAT(왼쪽축), 선=재문의율(오른쪽축)."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

cons = pd.read_csv("raw/ecommerce_consultations.csv", encoding="utf-8-sig")
sat = pd.read_csv("raw/ecommerce_satisfaction.csv", encoding="utf-8-sig")
df = sat.merge(cons, on=["consult_id", "customer_id"], how="left")

csat_by_channel = df.groupby("channel")["csat"].mean().sort_values()
recontact_by_channel = cons.groupby("channel")["is_recontact"].apply(lambda s: (s == "Y").mean() * 100)
order = csat_by_channel.index
recontact_by_channel = recontact_by_channel.reindex(order)

fig, ax1 = plt.subplots(figsize=(9, 6))
ax1.bar(order, csat_by_channel.values, color="#1e88e5", label="CSAT 평균 (왼쪽축)")
ax1.set_ylabel("CSAT 평균", color="#1e88e5")
ax1.set_ylim(0, 5)

ax2 = ax1.twinx()
ax2.plot(order, recontact_by_channel.values, color="#fb8c00", marker="o", linewidth=2, label="재문의율 (오른쪽축)")
ax2.set_ylabel("재문의율 (%)", color="#fb8c00")
ax2.set_ylim(0, 40)

lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

ax1.set_title("채널별 CSAT 평균 x 재문의율 결합차트")
plt.tight_layout()
plt.savefig("components/output/04_채널별_CSAT_재문의.png", dpi=120)
print("saved")
