# -*- coding: utf-8 -*-
"""컴포넌트①-보충: 부정비율 최고 대분류(결제/환불) 부정 VOC의 소분류별 분해 (가로 막대)."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv("raw/ecommerce_voc_synthetic_1000.csv", encoding="utf-8-sig")

sub = df[(df["대분류"] == "결제/환불") & (df["감정분류"] == "부정")]
counts = sub["소분류"].value_counts().sort_values(ascending=True)

fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.barh(counts.index, counts.values, color="#1e88e5")
for bar, v in zip(bars, counts.values):
    ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2, str(v), va="center")

ax.set_title(f"결제/환불 부정 VOC 유형 분해 (전체 {len(sub)}건)")
ax.set_xlabel("건수")
plt.tight_layout()
plt.savefig("components/output/01보충_결제환불_불만유형.png", dpi=120)
print("saved components/output/01보충_결제환불_불만유형.png")
