# -*- coding: utf-8 -*-
"""컴포넌트⑨ 교육 이수 여부(Y/N)별 CSAT·재문의율 비교 (subplot 2개, Y=강조색/N=회색)."""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

agents = pd.read_csv("raw/ecommerce_agents.csv", encoding="utf-8-sig")
cons = pd.read_csv("raw/ecommerce_consultations.csv", encoding="utf-8-sig")
sat = pd.read_csv("raw/ecommerce_satisfaction.csv", encoding="utf-8-sig")

merged = cons.merge(sat[["consult_id", "csat"]], on="consult_id", how="left")
per_agent = merged.groupby("agent_id").agg(
    csat_avg=("csat", "mean"),
    recontact_rate=("is_recontact", lambda s: (s == "Y").mean() * 100),
)
df = agents.merge(per_agent, on="agent_id", how="left")

g = df.groupby("training_completed_yn").agg(csat_avg=("csat_avg", "mean"), recontact_rate=("recontact_rate", "mean"))
labels = {"Y": "이수", "N": "미이수"}
colors = {"Y": "#2a78d6", "N": "#898781"}
order = ["Y", "N"]

fig = make_subplots(rows=1, cols=2, subplot_titles=("CSAT 평균", "재문의율(%)"))

fig.add_bar(
    x=[labels[k] for k in order], y=[round(g.loc[k, "csat_avg"], 2) for k in order],
    marker_color=[colors[k] for k in order],
    text=[f"{g.loc[k, 'csat_avg']:.2f}" for k in order], textposition="outside",
    row=1, col=1, showlegend=False,
)
fig.add_bar(
    x=[labels[k] for k in order], y=[round(g.loc[k, "recontact_rate"], 1) for k in order],
    marker_color=[colors[k] for k in order],
    text=[f"{g.loc[k, 'recontact_rate']:.1f}%" for k in order], textposition="outside",
    row=1, col=2, showlegend=False,
)

fig.update_layout(
    title="교육 이수 여부(Y/N)별 CSAT·재문의율 비교",
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=380,
)

fig.write_html("components/output/09_교육이수비교.html")
print("saved")
print(g)
