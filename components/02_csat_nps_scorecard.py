# -*- coding: utf-8 -*-
"""컴포넌트② CSAT·NPS 스코어카드: 4개 카드(CSAT평균/NPS평균/NPS점수+게이지/저만족비율)."""
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

sat = pd.read_csv("raw/ecommerce_satisfaction.csv", encoding="utf-8-sig")

csat_mean = sat["csat"].mean()
nps_mean = sat["nps"].mean()
promoter = (sat["nps"] >= 9).mean() * 100
detractor = (sat["nps"] <= 6).mean() * 100
nps_score = promoter - detractor
low_ratio = (sat["csat"] <= 2).mean() * 100

fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))
card_color = "#eceff1"

def card(ax, title, value_text, desc, value_color="#263238"):
    ax.set_facecolor(card_color)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#b0bec5")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.5, 0.78, title, ha="center", va="center", fontsize=12, color="#546e7a", transform=ax.transAxes, zorder=5)
    ax.text(0.5, 0.45, value_text, ha="center", va="center", fontsize=30, color=value_color, fontweight="bold", transform=ax.transAxes, zorder=5)
    ax.text(0.5, 0.15, desc, ha="center", va="center", fontsize=9, color="#78909c", transform=ax.transAxes, zorder=5)

card(axes[0], "CSAT 평균", f"{csat_mean:.2f} / 5", f"n={len(sat)}건")
card(axes[1], "NPS 평균", f"{nps_mean:.2f} / 10", "참고용 (평균 지표)")

nps_color = "#e53935" if nps_score < 0 else "#43a047"
card(axes[2], "NPS 점수", f"{nps_score:.1f}", "추천자%-비판자% (정식 계산)", value_color=nps_color)
ax_g = axes[2]
gauge_y = 0.02
ax_g.add_patch(plt.Rectangle((0.05, gauge_y), 0.9, 0.05, color="#cfd8dc", transform=ax_g.transAxes))
pos = 0.05 + 0.9 * ((nps_score + 100) / 200)
ax_g.plot([pos], [gauge_y + 0.025], marker="v", color=nps_color, markersize=12, transform=ax_g.transAxes, clip_on=False)

card(axes[3], "저만족 비율", f"{low_ratio:.1f}%", "csat 1~2점 비중", value_color="#e53935" if low_ratio > 20 else "#263238")

plt.savefig("components/output/02_csat_nps_scorecard.png", dpi=120, bbox_inches="tight")
print("saved")
print(f"CSAT={csat_mean:.2f} NPS평균={nps_mean:.2f} NPS점수={nps_score:.1f} 저만족비율={low_ratio:.1f}%")
