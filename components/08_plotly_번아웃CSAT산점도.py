# -*- coding: utf-8 -*-
"""컴포넌트⑧ 번아웃(초과근무)×CSAT 산점도 + 추세선(OLS).

주의(Day2 인사이트 반영): 이 프로젝트 데이터에서는 상관계수가 -0.32(p=0.17)로
교안 예시(-0.84, 유의함)와 달리 약하고 통계적으로 유의하지 않다. 그래서 그림 위
텍스트도 실제 값을 그대로 표시한다 — 강한 상관인 것처럼 과장하지 않는다.
"""
import pandas as pd
import plotly.express as px
from scipy import stats

agents = pd.read_csv("raw/ecommerce_agents.csv", encoding="utf-8-sig")
cons = pd.read_csv("raw/ecommerce_consultations.csv", encoding="utf-8-sig")
sat = pd.read_csv("raw/ecommerce_satisfaction.csv", encoding="utf-8-sig")

merged = cons.merge(sat[["consult_id", "csat"]], on="consult_id", how="left")
csat_by_agent = merged.groupby("agent_id")["csat"].mean().round(2)
df = agents.merge(csat_by_agent.rename("csat_avg"), on="agent_id", how="left")

r, p = stats.pearsonr(df["overtime_hours_avg"], df["csat_avg"])
significant = p < 0.05

fig = px.scatter(
    df, x="overtime_hours_avg", y="csat_avg", trendline="ols",
    hover_data={"agent_id": True, "overtime_hours_avg": True, "csat_avg": True},
    labels={"overtime_hours_avg": "월 평균 초과근무시간", "csat_avg": "상담원별 CSAT 평균"},
    title="번아웃(초과근무) x CSAT 산점도 + 추세선",
)
fig.update_traces(marker=dict(size=10, color="#2a78d6", line=dict(width=1, color="#0d366b")), selector=dict(mode="markers"))
fig.update_traces(line=dict(color="#eb6834", width=2), selector=dict(mode="lines"))

sig_text = "p<0.05, 유의함" if significant else "p≥0.05, 유의하지 않음"
fig.add_annotation(
    xref="paper", yref="paper", x=0.98, y=0.98, showarrow=False,
    text=f"r = {r:.2f} ({sig_text})",
    font=dict(size=14, color="#d03b3b" if not significant else "#0ca30c"),
    align="right",
)
fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=420)

fig.write_html("components/output/08_번아웃CSAT산점도.html")
print("saved")
print(f"r={r:.3f}, p={p:.4f}, significant(0.05)={significant}")
