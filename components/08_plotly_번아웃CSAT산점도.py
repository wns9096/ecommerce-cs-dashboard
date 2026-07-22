# -*- coding: utf-8 -*-
"""컴포넌트⑧ 번아웃(초과근무)×CSAT 산점도 + 추세선(OLS).

주의(Day2 인사이트 반영, 2026-07-22 갱신): 이 프로젝트 데이터에서는 상관계수가
-0.32(p=0.17)로 교안 예시(-0.84, 유의함)와 달리 약하고 통계적으로 유의하지 않다.
게다가 근속기간을 통제한 편상관은 -0.13(p=0.61)로 사실상 사라진다 — 즉 이 관계는
번아웃 자체보다 "신입 온보딩 기간"이라는 교란변수의 산물일 가능성이 높다. 점 색상을
근속기간(개월)으로 인코딩해 이 구조를 시각적으로도 드러낸다.
"""
import pandas as pd
import plotly.express as px
from scipy import stats

agents = pd.read_csv("raw/ecommerce_agents.csv", encoding="utf-8-sig")
agents["hire_date"] = pd.to_datetime(agents["hire_date"])
agents["tenure_months"] = ((pd.Timestamp("2025-12-31") - agents["hire_date"]).dt.days / 30.44).round(1)

cons = pd.read_csv("raw/ecommerce_consultations.csv", encoding="utf-8-sig")
sat = pd.read_csv("raw/ecommerce_satisfaction.csv", encoding="utf-8-sig")

merged = cons.merge(sat[["consult_id", "csat"]], on="consult_id", how="left")
csat_by_agent = merged.groupby("agent_id")["csat"].mean().round(2)
df = agents.merge(csat_by_agent.rename("csat_avg"), on="agent_id", how="left")

r, p = stats.pearsonr(df["overtime_hours_avg"], df["csat_avg"])
significant = p < 0.05


def partial_corr(x, y, z):
    rxy, _ = stats.pearsonr(x, y)
    rxz, _ = stats.pearsonr(x, z)
    ryz, _ = stats.pearsonr(y, z)
    r_p = (rxy - rxz * ryz) / (((1 - rxz ** 2) * (1 - ryz ** 2)) ** 0.5)
    n = len(x)
    t = r_p * ((n - 3) / (1 - r_p ** 2)) ** 0.5
    p_p = 2 * (1 - stats.t.cdf(abs(t), df=n - 3))
    return r_p, p_p


r_partial, p_partial = partial_corr(df["overtime_hours_avg"], df["csat_avg"], df["tenure_months"])

fig = px.scatter(
    df, x="overtime_hours_avg", y="csat_avg", trendline="ols",
    color="tenure_months", color_continuous_scale="Blues_r",
    hover_data={"agent_id": True, "overtime_hours_avg": True, "csat_avg": True, "tenure_months": True},
    labels={"overtime_hours_avg": "월 평균 초과근무시간", "csat_avg": "상담원별 CSAT 평균", "tenure_months": "근속(개월)"},
    title="번아웃(초과근무) x CSAT 산점도 + 추세선 (색=근속기간)",
)
fig.update_traces(marker=dict(size=10, line=dict(width=1, color="#0d366b")), selector=dict(mode="markers"))
fig.update_traces(line=dict(color="#eb6834", width=2), selector=dict(mode="lines"))

sig_text = "p<0.05, 유의함" if significant else "p≥0.05, 유의하지 않음"
note = f"r = {r:.2f} ({sig_text})<br>근속기간 통제 후: r = {r_partial:.2f} (p={p_partial:.2f})"
fig.add_annotation(
    xref="paper", yref="paper", x=0.98, y=0.98, showarrow=False, align="right",
    text=note,
    font=dict(size=13, color="#d03b3b" if not significant else "#0ca30c"),
)
fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=440)

fig.write_html("components/output/08_번아웃CSAT산점도.html")
print("saved")
print(f"r={r:.3f}, p={p:.4f}, significant(0.05)={significant}")
print(f"근속기간 통제 후 partial r={r_partial:.3f}, p={p_partial:.4f}")
