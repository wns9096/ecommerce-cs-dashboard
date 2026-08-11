# -*- coding: utf-8 -*-
"""5주차 Day3 — 지표 정의서(../my_LLM_Wiki/wiki/metrics/*.md)를 읽어 계산하는 스크립트.
BigQuery 대신 로컬 raw/ CSV를 직접 읽는다(4주차부터 이 프로젝트는 CSV로만 진행하기로
확정했고, 어차피 자동 실행 스크립트는 대화형 MCP에 의존하면 안 된다는 원칙과도 맞는다).

구조: 로더(load_specs/load_table) / 빌더+실행기(calc_side, calc_metric)로 분리.
지표를 추가할 때 이 파일을 수정하지 않아도 되는지 autopay_adoption_rate.md로 검증했다.
"""
import argparse
import glob
import os

import pandas as pd
import yaml

RAW = "raw"
METRICS_DIR = "../my_LLM_Wiki/wiki/metrics"

TABLE_FILES = {
    "customers": f"{RAW}/ecommerce_customers.csv",
    "usage_history": f"{RAW}/ecommerce_usage_history.csv",
    "product_events": f"{RAW}/data_product_events.csv",
    "customer_acquisition": f"{RAW}/data_customer_acquisition.csv",
    "membership_events": f"{RAW}/data_membership_events.csv",
    "marketing_spend": f"{RAW}/data_marketing_spend.csv",
    "referrals": f"{RAW}/data_referrals.csv",
    "consultations": f"{RAW}/ecommerce_consultations.csv",
    "satisfaction": f"{RAW}/ecommerce_satisfaction.csv",
    "voc": f"{RAW}/ecommerce_voc_synthetic_1000.csv",
}
DATE_COLS = {
    "customers": ["join_date", "churn_date"],
    "product_events": ["event_date"],
    "membership_events": ["event_date"],
    "referrals": ["referral_date", "reward_paid_date"],
    "consultations": ["consult_date"],
    "satisfaction": ["survey_date"],
}

_table_cache = {}


def load_table(name):
    if name not in _table_cache:
        df = pd.read_csv(TABLE_FILES[name], encoding="utf-8-sig")
        for c in DATE_COLS.get(name, []):
            if c in df.columns:
                df[c] = pd.to_datetime(df[c])
        _table_cache[name] = df
    return _table_cache[name]


def load_specs():
    specs = {}
    for path in sorted(glob.glob(f"{METRICS_DIR}/*.md")):
        base = os.path.basename(path)
        if base.startswith("_") or base == "README.md":
            continue
        text = open(path, encoding="utf-8").read()
        if not text.startswith("---"):
            continue
        _, fm, _ = text.split("---", 2)
        spec = yaml.safe_load(fm)
        specs[spec["metric_id"]] = spec
    return specs


def eval_condition(df, cond, params):
    if not cond:
        return pd.Series(True, index=df.index)
    ns = {col: df[col] for col in df.columns}
    ns.update(params)
    return eval(cond, {"__builtins__": {}}, ns)  # noqa: S307 — 내부 신뢰 명세 파일만 읽음


def aggregate(df, agg):
    agg = agg.strip()
    inner = agg[agg.index("(") + 1: agg.rindex(")")].strip() if "(" in agg else None
    if agg.upper().startswith("COUNT(DISTINCT"):
        col = inner.split(None, 1)[1].strip() if inner.upper().startswith("DISTINCT") else inner
        return df[col].nunique()
    if agg.upper() in ("COUNT(*)", "COUNT( * )"):
        return len(df)
    if agg.upper().startswith("SUM("):
        return df[inner].sum()
    if agg.upper().startswith("COUNT("):
        return df[inner].count()
    raise ValueError(f"지원하지 않는 집계식: {agg}")


def in_valid_range(spec, month):
    vr = spec.get("유효구간")
    if not vr:
        return True
    start, end = vr.get("시작"), vr.get("종료")
    if start and start != "전체" and month < start:
        return False
    if end and end != "전체" and month > end:
        return False
    return True


def calc_side(side_spec, params):
    table = load_table(side_spec["테이블"])
    mask = eval_condition(table, side_spec.get("조건"), params)
    return aggregate(table[mask], side_spec["집계"])


def calc_metric(metric_id, month, specs, results):
    if metric_id in results:
        return results[metric_id]
    if metric_id not in specs:
        raise KeyError(f"정의서를 찾을 수 없음: {metric_id}")
    spec = specs[metric_id]

    if not in_valid_range(spec, month):
        results[metric_id] = {"value": None, "flag": "유효구간 밖"}
        return results[metric_id]

    m_start = pd.Timestamp(f"{month}-01")
    m_end = m_start + pd.offsets.MonthEnd(0)
    params = {"month_start": m_start, "month_end": m_end, "month": month}

    def resolve(side):
        if "metric" in side:
            return calc_metric(side["metric"], month, specs, results)["value"]
        return calc_side(side, params)

    유형 = spec["유형"]
    if 유형 == "비율형":
        분모 = resolve(spec["분모"])
        분자 = resolve(spec["분자"])
        value = (분자 / 분모) if 분모 else None
        n = 분모
    elif 유형 == "집계형":
        target = spec.get("대상", spec.get("분자"))
        value = calc_side(target, params)
        n = value
    elif 유형 == "파생형":
        분모 = resolve(spec["분모"])
        분자 = resolve(spec["분자"])
        value = (분자 / 분모) if 분모 else None
        n = 분모
    else:
        raise ValueError(f"알 수 없는 유형: {유형}")

    flag = None
    min_n = spec.get("최소표본")
    if min_n and n is not None and n < min_n:
        flag = "표본부족"
    results[metric_id] = {"value": value, "flag": flag}
    return results[metric_id]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    args = ap.parse_args()

    specs = load_specs()
    results = {}
    rows = []
    for metric_id, spec in specs.items():
        if spec.get("유형", "").endswith("(차원분해)"):
            continue  # channel_cac_* 등은 단일 시계열 스칼라가 아니므로 이 스크립트 대상 아님
        try:
            r = calc_metric(metric_id, args.month, specs, results)
            rows.append({"metric_id": metric_id, "month": args.month, "value": r["value"], "flag": r["flag"]})
        except Exception as e:  # noqa: BLE001 — 실패한 지표도 결과표에 남겨야 함
            rows.append({"metric_id": metric_id, "month": args.month, "value": None, "flag": f"오류: {e}"})

    out = pd.DataFrame(rows)
    os.makedirs("outputs", exist_ok=True)
    out_path = f"outputs/metrics_{args.month.replace('-', '')}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))
    print(f"saved {out_path}")


if __name__ == "__main__":
    main()
