# -*- coding: utf-8 -*-
"""컴포넌트① 불만 유형 현황: 대분류별 전체/부정 건수 막대 + 월별 전체/부정 추이 꺾은선."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv("raw/ecommerce_voc_synthetic_1000.csv", encoding="utf-8-sig")
df["접수일시"] = pd.to_datetime(df["접수일시"])
df["month"] = df["접수일시"].dt.to_period("M").astype(str)

cat = df.groupby("대분류").agg(전체건수=("voc_id", "count"), 부정건수=("감정분류", lambda s: (s == "부정").sum()))
cat = cat.sort_values("전체건수", ascending=False)

mon = df.groupby("month").agg(전체건수=("voc_id", "count"), 부정건수=("감정분류", lambda s: (s == "부정").sum()))

fig, axes = plt.subplots(1, 2, figsize=(15, 6))

ax = axes[0]
x = range(len(cat))
ax.bar(x, cat["전체건수"], color="#cfd8dc", label="전체 건수")
ax.bar(x, cat["부정건수"], color="#e53935", label="부정 건수")
ax.set_xticks(list(x))
ax.set_xticklabels(cat.index, rotation=30, ha="right")
ax.set_title("대분류별 전체·부정 VOC 건수")
ax.legend()

ax2 = axes[1]
ax2.plot(mon.index, mon["전체건수"], marker="o", color="#1e88e5", label="전체 건수")
ax2.plot(mon.index, mon["부정건수"], marker="o", color="#e53935", label="부정 건수")
ax2.set_xticks(range(0, len(mon.index), 2))
ax2.set_xticklabels(mon.index[::2], rotation=45, ha="right")
ax2.set_title("월별 전체·부정 VOC 추이 (2024~2025)")
ax2.legend()

plt.tight_layout()
plt.savefig("components/output/01_voc_overview.png", dpi=120)
print("saved components/output/01_voc_overview.png")
