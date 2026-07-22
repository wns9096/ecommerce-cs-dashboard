# -*- coding: utf-8 -*-
"""3주차 Day5 전처리 종합 실습: 지저분한 교육 이수 로그(raw/data_agent_training_log_raw.csv)를
정제해 raw/data_agent_training_log_clean.csv로 저장하고, 처리 규칙에 따른 건수를 리포트한다.

처리 규칙 (사람이 먼저 정한 것 — 임의 보정 없이 원칙대로만 처리):
- agent_id: 대문자로 통일 + 앞뒤 공백 제거
- completed_date: YYYY-MM-DD로 통일, 변환 불가능한 값은 결측 처리
- score: 숫자로 변환, 0~100을 벗어나거나 문자(예: "미응시")인 값은 결측 처리(임의 보정 금지)
- status: 완료/complete/이수/Y -> 이수 / 미완료/N/미이수/빈칸 -> 미이수
- 중복: agent_id·course·completed_date·score·status가 완전히 같은 행은 1건만 남김
"""
import pandas as pd

RAW_PATH = "raw/data_agent_training_log_raw.csv"
CLEAN_PATH = "raw/data_agent_training_log_clean.csv"

STATUS_MAP = {
    "완료": "이수", "complete": "이수", "이수": "이수", "Y": "이수",
    "미완료": "미이수", "N": "미이수", "미이수": "미이수",
}


def parse_date(v):
    if pd.isna(v) or v == "":
        return pd.NaT
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m-%d-%Y", "%Y%m%d"):
        try:
            return pd.to_datetime(v, format=fmt)
        except ValueError:
            continue
    return pd.NaT


def clean_score(v):
    if pd.isna(v) or v == "":
        return None
    try:
        f = float(v)
    except ValueError:
        return None
    return f if 0 <= f <= 100 else None


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = raw.copy()
    n0 = len(df)

    df["agent_id"] = df["agent_id"].str.strip().str.upper()

    before = len(df)
    df = df.drop_duplicates(subset=["agent_id", "course", "completed_date", "score", "status"])
    dup_removed = before - len(df)

    date_missing_before = df["completed_date"].isna().sum()
    df["completed_date"] = df["completed_date"].apply(parse_date)
    date_missing_after = df["completed_date"].isna().sum()

    score_missing_before = df["score"].isna().sum()
    df["score"] = df["score"].apply(clean_score)
    score_missing_after = df["score"].isna().sum()

    df["status"] = df["status"].map(STATUS_MAP).fillna("미이수")

    report = {
        "원본 행 수": n0,
        "중복 제거": dup_removed,
        "정제 후 행 수": len(df),
        "날짜 결측(원본)": int(date_missing_before),
        "날짜 결측(정제 후, 변환 불가 포함)": int(date_missing_after),
        "score 결측(원본)": int(score_missing_before),
        "score 결측(정제 후, 문자·범위밖 포함)": int(score_missing_after),
    }
    return df, report


if __name__ == "__main__":
    raw = pd.read_csv(RAW_PATH, encoding="utf-8-sig", dtype=str)
    clean_df, report = clean(raw)
    clean_df.to_csv(CLEAN_PATH, index=False, encoding="utf-8-sig")

    print("=== 정제 리포트 ===")
    for k, v in report.items():
        print(f"- {k}: {v}")

    final = (
        clean_df.sort_values("log_id")
        .drop_duplicates(subset=["agent_id"], keep="last")[["agent_id", "status"]]
        .sort_values("agent_id")
    )
    print(f"\nCS 기본과정 최종 이수: 이수 {(final.status == '이수').sum()}명 / 미이수 {(final.status == '미이수').sum()}명")

    try:
        agents = pd.read_csv("raw/ecommerce_agents.csv", encoding="utf-8-sig")
        check = agents[["agent_id", "training_completed_yn"]].merge(final, on="agent_id")
        check["clean_yn"] = check["status"].map({"이수": "Y", "미이수": "N"})
        mismatch = check[check["training_completed_yn"] != check["clean_yn"]]
        print(f"BigQuery training_completed_yn 대조 — 불일치: {len(mismatch)}건")
        if len(mismatch):
            print(mismatch)
    except FileNotFoundError:
        print("raw/ecommerce_agents.csv 없음 — 대조 검증 생략")
