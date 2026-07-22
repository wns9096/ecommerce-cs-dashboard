# -*- coding: utf-8 -*-
"""컴포넌트⑦ 직원만족도 eNPS 스코어카드: 전체 게이지 1개 + 팀별 작은 지표 카드 3개.

실행 환경 참고: 이 저장소엔 kaleido가 설치돼 있지 않아 fig.show()로 브라우저를
띄우는 대신 components/output/07_직원만족도eNPS스코어카드.html로 저장한다
(01~06 컴포넌트의 PNG 산출물과 같은 역할 — 더블클릭하면 그대로 인터랙티브하게 열림).
"""
import pandas as pd
import plotly.graph_objects as go

agents = pd.read_csv("raw/ecommerce_agents.csv", encoding="utf-8-sig")


def enps(df):
    promoter = (df["agent_satisfaction"] >= 9).mean() * 100
    detractor = (df["agent_satisfaction"] <= 6).mean() * 100
    return round(promoter - detractor, 1)


overall_enps = enps(agents)
team_enps = agents.groupby("team").apply(enps, include_groups=False).to_dict()

fig = go.Figure()

fig.add_trace(go.Indicator(
    mode="gauge+number",
    value=overall_enps,
    title={"text": "전체 eNPS"},
    domain={"x": [0, 0.55], "y": [0, 1]},
    gauge={
        "axis": {"range": [-100, 100]},
        "bar": {"color": "#1c2733"},
        "steps": [
            {"range": [-100, 0], "color": "#f6c6c6"},
            {"range": [0, 100], "color": "#c8e6c9"},
        ],
    },
))

# 팀별 작은 숫자 카드 3개 — Indicator를 delta 없이 숫자만 표시하는 형태로 나란히 배치
team_order = ["1팀", "2팀", "3팀"]
for i, team in enumerate(team_order):
    val = team_enps.get(team, 0)
    fig.add_trace(go.Indicator(
        mode="number",
        value=val,
        title={"text": team},
        number={"suffix": "", "font": {"color": "#d03b3b" if val == min(team_enps.values()) else "#1c2733"}},
        domain={"x": [0.62, 1.0], "y": [1 - (i + 1) / 3 + 0.05, 1 - i / 3 - 0.05]},
    ))

fig.update_layout(
    title=f"직원만족도 eNPS 스코어카드 (전체 {overall_enps} / 팀별 최저 {min(team_enps.values())})",
    height=380,
    paper_bgcolor="rgba(0,0,0,0)",
)

fig.write_html("components/output/07_직원만족도eNPS스코어카드.html")
print("saved")
print(f"전체 eNPS={overall_enps}, 팀별={team_enps}")
