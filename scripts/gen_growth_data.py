# -*- coding: utf-8 -*-
"""4주차 Day3 — 설계서(wiki/data/신규_성장데이터_설계서_이커머스.md) 기반 성장 데이터 5종 생성.
시드 고정, 기존 raw/ecommerce_customers.csv의 실제 customer_id/join_date/churn_yn/churn_date/membership_grade만 사용.
정합성 규칙을 스크립트 내에서 자체 검사하고, 위반 시 저장하지 않는다.
"""
import datetime as dt

import numpy as np
import pandas as pd

RAW = "raw"
SEED = 42
rng = np.random.default_rng(SEED)

CHANNELS = ["SNS광고", "검색광고", "자사앱푸시", "지인추천", "제휴사", "오프라인매장"]
CHANNEL_PROPS = {"SNS광고": 0.32, "검색광고": 0.20, "자사앱푸시": 0.12, "지인추천": 0.18, "제휴사": 0.10, "오프라인매장": 0.08}
ONLINE_CHANNELS = {"SNS광고", "검색광고", "자사앱푸시"}
NON_AD_CHANNELS = {"지인추천", "제휴사", "오프라인매장"}

COST_PARAMS = {  # (평균, 표준편차) - 로그정규 근사를 위해 정수 clip
    "SNS광고": (150000, 35000),
    "검색광고": (55000, 15000),
    "자사앱푸시": (9000, 2500),
    "지인추천": (2900, 700),
    "제휴사": (25000, 7000),
    "오프라인매장": (48000, 12000),
}

CTR_PARAMS = {  # 채널별 (노출 대비 클릭률, 클릭 대비 가입 전환율) - SNS는 클릭 많고 전환 낮은 허영지표 패턴
    "SNS광고": (0.020, 0.006),
    "검색광고": (0.055, 0.030),
    "자사앱푸시": (0.090, 0.045),
}

DEVICES = ["모바일앱", "모바일웹", "PC웹"]
GRADES_ORDER = ["일반", "BRONZE", "SILVER", "GOLD", "VIP"]
FEATURES = ["첫주문", "장바구니담기", "리뷰작성", "쿠폰다운로드", "위시리스트추가", "앱푸시동의", "자동결제등록"]


def load_customers():
    df = pd.read_csv(f"{RAW}/ecommerce_customers.csv", encoding="utf-8-sig")
    df["join_date"] = pd.to_datetime(df["join_date"])
    df["churn_date"] = pd.to_datetime(df["churn_date"])
    return df


def gen_acquisition(cust):
    n = len(cust)
    counts = {ch: int(round(CHANNEL_PROPS[ch] * n)) for ch in CHANNELS}
    diff = n - sum(counts.values())
    counts["SNS광고"] += diff  # 반올림 오차는 최대 채널에 흡수
    channels = []
    for ch in CHANNELS:
        channels += [ch] * counts[ch]
    channels = np.array(channels)
    rng.shuffle(channels)

    rows = []
    for cid, ch in zip(cust["customer_id"], channels):
        mean, sd = COST_PARAMS[ch]
        cost = int(np.clip(rng.normal(mean, sd), mean * 0.3, mean * 2.2))
        campaign = None
        if ch not in NON_AD_CHANNELS:
            campaign = rng.choice([f"{ch}_2024_A", f"{ch}_2024_B", f"{ch}_시즌프로모션"])
        device = rng.choice(DEVICES, p=[0.55, 0.30, 0.15])
        rows.append({
            "customer_id": cid,
            "acquisition_channel": ch,
            "acquisition_campaign": campaign,
            "acquisition_cost": cost,
            "signup_device": device,
        })
    acq = pd.DataFrame(rows)
    return acq.set_index("customer_id").loc[cust["customer_id"]].reset_index()


def gen_marketing_spend(cust, acq):
    merged = cust[["customer_id", "join_date"]].merge(acq, on="customer_id")
    merged["month"] = merged["join_date"].dt.strftime("%Y-%m")
    months = pd.period_range(cust["join_date"].min().to_period("M"), cust["join_date"].max().to_period("M"), freq="M")
    months = [str(m) for m in months]

    grp = merged.groupby(["month", "acquisition_channel"]).agg(signups=("customer_id", "count"), spend_actual=("acquisition_cost", "sum")).reset_index()

    rows = []
    for month in months:
        for ch in CHANNELS:
            sub = grp[(grp["month"] == month) & (grp["acquisition_channel"] == ch)]
            signups = int(sub["signups"].sum())
            spend_from_acq = int(sub["spend_actual"].sum())
            overhead = 1.0 + rng.uniform(0.05, 0.20)
            spend = int(spend_from_acq * overhead) if signups > 0 else int(rng.uniform(0, COST_PARAMS[ch][0] * 0.5))
            impressions, clicks = None, None
            if ch in ONLINE_CHANNELS:
                ctr, conv = CTR_PARAMS[ch]
                # signups = impressions * ctr * conv  ->  impressions 역산 (0 가입도 소량 노출은 있을 수 있음)
                base_impr = int(spend / (COST_PARAMS[ch][0] / 3000)) if spend > 0 else 0
                impressions = max(base_impr, int(signups / max(ctr * conv, 1e-6)) if signups > 0 else base_impr)
                impressions = int(impressions * rng.uniform(0.85, 1.15))
                clicks = int(impressions * ctr * rng.uniform(0.7, 1.3))
                clicks = max(clicks, signups)
            rows.append({"month": month, "channel": ch, "spend": spend, "impressions": impressions, "clicks": clicks, "signups": signups})
    return pd.DataFrame(rows)


def gen_referrals(cust, acq):
    referred_pool = acq[acq["acquisition_channel"] == "지인추천"]["customer_id"].tolist()
    rng.shuffle(referred_pool)
    n_ref = len(referred_pool)

    non_churn_ids = cust[cust["churn_yn"] == "N"]["customer_id"].tolist()
    all_ids = cust["customer_id"].tolist()
    cust_idx = cust.set_index("customer_id")

    # 추천 건수 롱테일 분포: 1건이 대부분, 소수만 다건 (심을 패턴: 2건 이상 추천자는 이탈 안 함 -> 비churn 풀에서만 뽑음)
    referrers = []
    i = 0
    while i < n_ref:
        remaining = n_ref - i
        r = rng.random()
        if remaining >= 4 and r < 0.05:
            k = int(rng.integers(3, 5))
            referrer = rng.choice(non_churn_ids)
        elif remaining >= 2 and r < 0.20:
            k = 2
            referrer = rng.choice(non_churn_ids)
        else:
            k = 1
            referrer = rng.choice(all_ids)
        k = min(k, remaining)
        referrers += [referrer] * k
        i += k

    rows = []
    for idx, (referred, referrer) in enumerate(zip(referred_pool, referrers)):
        if referrer == referred:
            candidates = [c for c in all_ids if c != referred]
            referrer = rng.choice(candidates)
        referred_join = cust_idx.loc[referred, "join_date"]
        lag_days = int(rng.integers(1, 60))
        referral_date = referred_join - pd.Timedelta(days=lag_days)
        reward_amount = int(rng.choice([3000, 5000, 7000, 10000], p=[0.35, 0.30, 0.20, 0.15]))
        paid = rng.random() < 0.85
        reward_paid_date = None
        if paid:
            pay_lag = int(rng.integers(7, 45))
            reward_paid_date = referred_join + pd.Timedelta(days=pay_lag)
        rows.append({
            "referral_id": f"REF{idx+1:04d}",
            "referrer_customer_id": referrer,
            "referred_customer_id": referred,
            "referral_date": referral_date,
            "reward_amount": reward_amount,
            "reward_paid_date": reward_paid_date,
        })
    return pd.DataFrame(rows)


def gen_product_events(cust, acq):
    device_map = acq.set_index("customer_id")["signup_device"]
    rows = []
    eid = 1
    for _, row in cust.iterrows():
        cid = row["customer_id"]
        join = row["join_date"]
        is_churn = row["churn_yn"] == "Y"
        device = device_map[cid]

        # 심을 패턴: 비이탈 고객은 75% 확률로 7일 내 첫주문, 이탈 고객은 25% 확률
        early_prob = 0.75 if not is_churn else 0.25
        r = rng.random()
        if r < early_prob:
            first_order_day = int(rng.integers(0, 7))
        elif rng.random() < 0.5:
            first_order_day = int(rng.integers(7, 30))
        else:
            first_order_day = None

        if first_order_day is not None:
            rows.append({"event_id": None, "customer_id": cid, "event_date": join + pd.Timedelta(days=first_order_day),
                         "days_since_signup": first_order_day, "feature": "첫주문", "signup_device": device})

        n_other = int(rng.poisson(2.2))
        other_features = rng.choice([f for f in FEATURES if f != "첫주문"], size=min(n_other, 15))
        for feat in other_features:
            day = int(rng.integers(0, 30))
            rows.append({"event_id": None, "customer_id": cid, "event_date": join + pd.Timedelta(days=day),
                         "days_since_signup": day, "feature": feat, "signup_device": device})

    df = pd.DataFrame(rows).sort_values(["customer_id", "event_date"]).reset_index(drop=True)
    df["event_id"] = [f"PE{i+1:05d}" for i in range(len(df))]
    return df[["event_id", "customer_id", "event_date", "days_since_signup", "feature", "signup_device"]]


def gen_membership_events(cust):
    rows = []
    eid = 1
    for _, row in cust.iterrows():
        cid = row["customer_id"]
        join = row["join_date"]
        grade = row["membership_grade"]
        is_churn = row["churn_yn"] == "Y"
        churn_date = row["churn_date"]

        rows.append({"event_id": None, "customer_id": cid, "event_date": join, "event_type": "가입",
                     "from_grade": None, "to_grade": "일반" if grade != "일반" else grade})

        last_grade = "일반"
        if grade != "일반":
            span_days = 30
            if is_churn and pd.notna(churn_date):
                span_days = max(int((churn_date - join).days) - 1, 1)
            up_day = int(rng.integers(1, max(span_days, 2)))
            up_date = join + pd.Timedelta(days=up_day)
            rows.append({"event_id": None, "customer_id": cid, "event_date": up_date, "event_type": "등급상승",
                         "from_grade": "일반", "to_grade": grade})
            last_grade = grade

        if is_churn and pd.notna(churn_date):
            rows.append({"event_id": None, "customer_id": cid, "event_date": churn_date, "event_type": "이탈",
                         "from_grade": last_grade, "to_grade": None})

    df = pd.DataFrame(rows).sort_values(["customer_id", "event_date"]).reset_index(drop=True)
    df["event_id"] = [f"ME{i+1:05d}" for i in range(len(df))]
    return df[["event_id", "customer_id", "event_date", "event_type", "from_grade", "to_grade"]]


def validate(cust, acq, spend, product_events, membership_events, referrals):
    errors = []
    cust_ids = set(cust["customer_id"])

    if set(acq["customer_id"]) != cust_ids or len(acq) != len(cust):
        errors.append("acquisition: customer_id 집합/행수 불일치")
    if not acq["acquisition_channel"].isin(CHANNELS).all():
        errors.append("acquisition: 미정의 채널 존재")
    ad_mask = acq["acquisition_channel"].isin(NON_AD_CHANNELS)
    if acq.loc[ad_mask, "acquisition_campaign"].notna().any():
        errors.append("acquisition: 비광고 채널인데 campaign 값 존재")
    if acq.loc[~ad_mask, "acquisition_campaign"].isna().any():
        errors.append("acquisition: 광고 채널인데 campaign 결측")
    if (acq["acquisition_cost"] <= 0).any():
        errors.append("acquisition: cost <= 0 존재")

    referred_set = set(referrals["referred_customer_id"])
    acq_referral_set = set(acq[acq["acquisition_channel"] == "지인추천"]["customer_id"])
    if referred_set != acq_referral_set:
        errors.append("referrals: referred_customer_id 집합이 acquisition의 지인추천과 불일치")
    if referrals["referred_customer_id"].duplicated().any():
        errors.append("referrals: referred_customer_id 중복 존재")
    if (referrals["referrer_customer_id"] == referrals["referred_customer_id"]).any():
        errors.append("referrals: 자기추천 존재")
    join_map = cust.set_index("customer_id")["join_date"]
    ref_check = referrals.merge(join_map.rename("referred_join"), left_on="referred_customer_id", right_index=True)
    if (ref_check["referral_date"] > ref_check["referred_join"]).any():
        errors.append("referrals: referral_date가 피추천인 join_date보다 늦음")
    paid = referrals.dropna(subset=["reward_paid_date"])
    if (paid["reward_paid_date"] <= paid["referral_date"]).any():
        errors.append("referrals: reward_paid_date가 referral_date보다 빠름")

    if not set(product_events["customer_id"]).issubset(cust_ids):
        errors.append("product_events: 참조무결성 위반")
    pe_check = product_events.merge(join_map.rename("join_date"), left_on="customer_id", right_index=True)
    computed_days = (pe_check["event_date"] - pe_check["join_date"]).dt.days
    if not (computed_days == pe_check["days_since_signup"]).all():
        errors.append("product_events: days_since_signup 불일치")
    if not pe_check["days_since_signup"].between(0, 29).all():
        errors.append("product_events: days_since_signup 범위(0~29) 위반")
    if not product_events["feature"].isin(FEATURES).all():
        errors.append("product_events: 미정의 feature 존재")

    if not set(membership_events["customer_id"]).issubset(cust_ids):
        errors.append("membership_events: 참조무결성 위반")
    first_ev = membership_events.sort_values("event_date").groupby("customer_id").first()
    if not (first_ev["event_type"] == "가입").all():
        errors.append("membership_events: 첫 이벤트가 가입이 아닌 고객 존재")
    churned = cust[cust["churn_yn"] == "Y"].set_index("customer_id")
    last_ev = membership_events.sort_values("event_date").groupby("customer_id").last()
    for cid in churned.index:
        if last_ev.loc[cid, "event_type"] != "이탈":
            errors.append(f"membership_events: {cid} 이탈 고객인데 마지막 이벤트가 이탈이 아님")
            break
    for cid, grade in cust.set_index("customer_id")["membership_grade"].items():
        non_churn_last = membership_events[(membership_events["customer_id"] == cid) & (membership_events["event_type"] != "이탈")]
        final_to = non_churn_last.sort_values("event_date")["to_grade"].iloc[-1]
        if final_to != grade:
            errors.append(f"membership_events: {cid} 최종 등급 불일치 (기대 {grade}, 실제 {final_to})")
            break

    signup_sum = spend.groupby("channel")["signups"].sum()
    acq_sum = acq.groupby("acquisition_channel")["customer_id"].count()
    for ch in CHANNELS:
        if int(signup_sum.get(ch, 0)) != int(acq_sum.get(ch, 0)):
            errors.append(f"marketing_spend: {ch} signups 합계 불일치 (spend={signup_sum.get(ch,0)}, acq={acq_sum.get(ch,0)})")
    ad_rows = spend[spend["channel"].isin(ONLINE_CHANNELS)]
    if (ad_rows["clicks"] > ad_rows["impressions"]).any():
        errors.append("marketing_spend: clicks > impressions 존재")
    non_ad_rows = spend[spend["channel"].isin(NON_AD_CHANNELS)]
    if non_ad_rows["impressions"].notna().any() or non_ad_rows["clicks"].notna().any():
        errors.append("marketing_spend: 비광고 채널에 impressions/clicks 값 존재")

    return errors


def main():
    cust = load_customers()
    acq = gen_acquisition(cust)
    referrals = gen_referrals(cust, acq)
    spend = gen_marketing_spend(cust, acq)
    product_events = gen_product_events(cust, acq)
    membership_events = gen_membership_events(cust)

    errors = validate(cust, acq, spend, product_events, membership_events, referrals)
    if errors:
        print("검증 실패 — 저장하지 않음:")
        for e in errors:
            print(" -", e)
        raise SystemExit(1)

    for df, col in [(acq, None), (referrals, ["referral_date", "reward_paid_date"]), (product_events, ["event_date"]), (membership_events, ["event_date"])]:
        pass

    acq.to_csv(f"{RAW}/data_customer_acquisition.csv", index=False, encoding="utf-8-sig")
    spend.to_csv(f"{RAW}/data_marketing_spend.csv", index=False, encoding="utf-8-sig")
    product_events_out = product_events.copy()
    product_events_out["event_date"] = product_events_out["event_date"].dt.strftime("%Y-%m-%d")
    product_events_out.to_csv(f"{RAW}/data_product_events.csv", index=False, encoding="utf-8-sig")
    membership_events_out = membership_events.copy()
    membership_events_out["event_date"] = membership_events_out["event_date"].dt.strftime("%Y-%m-%d")
    membership_events_out.to_csv(f"{RAW}/data_membership_events.csv", index=False, encoding="utf-8-sig")
    referrals_out = referrals.copy()
    referrals_out["referral_date"] = referrals_out["referral_date"].dt.strftime("%Y-%m-%d")
    referrals_out["reward_paid_date"] = referrals_out["reward_paid_date"].apply(lambda x: x.strftime("%Y-%m-%d") if pd.notna(x) else "")
    referrals_out.to_csv(f"{RAW}/data_referrals.csv", index=False, encoding="utf-8-sig")

    print("검증 통과, 생성 완료")
    print(f"data_customer_acquisition.csv: {len(acq)}행")
    print(acq["acquisition_channel"].value_counts())
    print(f"\ndata_marketing_spend.csv: {len(spend)}행")
    print(f"\ndata_product_events.csv: {len(product_events)}행")
    print(product_events["feature"].value_counts())
    print(f"\ndata_membership_events.csv: {len(membership_events)}행")
    print(membership_events["event_type"].value_counts())
    print(f"\ndata_referrals.csv: {len(referrals)}행")
    print("추천 건수 분포:")
    print(referrals["referrer_customer_id"].value_counts().value_counts().sort_index())


if __name__ == "__main__":
    main()
