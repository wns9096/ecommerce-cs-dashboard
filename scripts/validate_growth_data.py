# -*- coding: utf-8 -*-
"""4주차 Day3 — 독립 검증. gen_growth_data.py를 보지 않고, 설계서(wiki)의 규칙만 보고
CSV 파일 자체를 다시 읽어서 검사한다. (생성 주체 != 검증 주체)
"""
import pandas as pd

RAW = "raw"


def load():
    cust = pd.read_csv(f"{RAW}/ecommerce_customers.csv", encoding="utf-8-sig", parse_dates=["join_date", "churn_date"])
    acq = pd.read_csv(f"{RAW}/data_customer_acquisition.csv", encoding="utf-8-sig")
    spend = pd.read_csv(f"{RAW}/data_marketing_spend.csv", encoding="utf-8-sig")
    pe = pd.read_csv(f"{RAW}/data_product_events.csv", encoding="utf-8-sig", parse_dates=["event_date"])
    me = pd.read_csv(f"{RAW}/data_membership_events.csv", encoding="utf-8-sig", parse_dates=["event_date"])
    ref = pd.read_csv(f"{RAW}/data_referrals.csv", encoding="utf-8-sig", parse_dates=["referral_date", "reward_paid_date"])
    return cust, acq, spend, pe, me, ref


def section(title):
    print(f"\n{'='*10} {title} {'='*10}")


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    return cond


def main():
    cust, acq, spend, pe, me, ref = load()
    cust_ids = set(cust["customer_id"])

    section("1. 정합성 검증")
    check("acq: 366명 전원 1행씩", set(acq["customer_id"]) == cust_ids and len(acq) == 366)
    check("acq: 채널값 6종만", acq["acquisition_channel"].isin(
        ["SNS광고", "검색광고", "자사앱푸시", "지인추천", "제휴사", "오프라인매장"]).all())
    non_ad = acq["acquisition_channel"].isin(["지인추천", "제휴사", "오프라인매장"])
    check("acq: 비광고채널 campaign 전부 결측", acq.loc[non_ad, "acquisition_campaign"].isna().all())
    check("acq: 광고채널 campaign 전부 존재", acq.loc[~non_ad, "acquisition_campaign"].notna().all())

    referred = set(ref["referred_customer_id"])
    acq_referral = set(acq[acq["acquisition_channel"] == "지인추천"]["customer_id"])
    check("referrals: referred == acquisition의 지인추천 집합", referred == acq_referral,
          f"차집합 {referred ^ acq_referral}")
    check("referrals: referred_customer_id 중복 없음", not ref["referred_customer_id"].duplicated().any())
    check("referrals: 자기추천 없음", (ref["referrer_customer_id"] != ref["referred_customer_id"]).all())
    ref2 = ref.merge(cust[["customer_id", "join_date"]], left_on="referred_customer_id", right_on="customer_id")
    check("referrals: referral_date <= 피추천인 join_date", (ref2["referral_date"] <= ref2["join_date"]).all())
    paid = ref.dropna(subset=["reward_paid_date"])
    check("referrals: reward_paid_date > referral_date (지급건만)", (paid["reward_paid_date"] > paid["referral_date"]).all())
    check("referrals: 미지급 건 존재(구조적 결측)", ref["reward_paid_date"].isna().any(),
          f"{ref['reward_paid_date'].isna().sum()}건 미지급")

    check("product_events: customer_id 참조무결성", set(pe["customer_id"]).issubset(cust_ids))
    pe2 = pe.merge(cust[["customer_id", "join_date"]], on="customer_id")
    computed = (pe2["event_date"] - pe2["join_date"]).dt.days
    check("product_events: days_since_signup == event_date - join_date", (computed == pe2["days_since_signup"]).all())
    check("product_events: days_since_signup 0~29 범위", pe["days_since_signup"].between(0, 29).all())

    check("membership_events: customer_id 참조무결성", set(me["customer_id"]).issubset(cust_ids))
    first_ev = me.sort_values("event_date").groupby("customer_id").first()
    check("membership_events: 모든 고객 첫 이벤트 = 가입", (first_ev["event_type"] == "가입").all())
    churned_ids = cust[cust["churn_yn"] == "Y"]["customer_id"]
    last_ev = me.sort_values("event_date").groupby("customer_id").last()
    check("membership_events: 이탈고객 마지막 이벤트 = 이탈", (last_ev.loc[churned_ids, "event_type"] == "이탈").all())
    non_churn_final = me[me["event_type"] != "이탈"].sort_values("event_date").groupby("customer_id").last()["to_grade"]
    grade_match = cust.set_index("customer_id")["membership_grade"].reindex(non_churn_final.index) == non_churn_final
    check("membership_events: 최종 등급이 customers.membership_grade와 일치", grade_match.all(),
          f"불일치 {(~grade_match).sum()}건")

    signup_sum = spend.groupby("channel")["signups"].sum()
    acq_sum = acq.groupby("acquisition_channel")["customer_id"].count()
    signup_match = all(int(signup_sum.get(ch, 0)) == int(acq_sum.get(ch, 0)) for ch in acq_sum.index)
    check("marketing_spend: 채널별 signups 합계 == acquisition 채널별 인원수", signup_match)
    online = spend[spend["channel"].isin(["SNS광고", "검색광고", "자사앱푸시"])]
    check("marketing_spend: 온라인채널 clicks <= impressions", (online["clicks"] <= online["impressions"]).all())
    offline = spend[spend["channel"].isin(["지인추천", "제휴사", "오프라인매장"])]
    check("marketing_spend: 비광고채널 impressions/clicks 전부 결측", offline["impressions"].isna().all() and offline["clicks"].isna().all())

    section("2. 검증 코드 자가 점검 (컬럼 혼동·결측 누락 여부)")
    print("- referral_date 비교: 날짜 타입(datetime64)으로 파싱 후 비교함 (문자열 비교 아님)")
    print(f"- referral_date dtype: {ref['referral_date'].dtype}, join_date dtype: {cust['join_date'].dtype}")
    print("- 비교 대상이 '피추천인'의 join_date인지 재확인: merge key = referred_customer_id (referrer_customer_id 아님) — 확인됨")
    print(f"- reward_paid_date 결측 {ref['reward_paid_date'].isna().sum()}건은 비교에서 자동 제외(dropna) — '위반 0건'이 아니라 애초에 검사 대상에서 뺀 것임을 명시")

    section("3. 패턴 검증")
    pe_first_order = pe[pe["feature"] == "첫주문"].groupby("customer_id")["days_since_signup"].min()
    cust2 = cust.set_index("customer_id").copy()
    cust2["first_order_day"] = pe_first_order
    def group(row):
        if pd.isna(row["first_order_day"]):
            return "첫주문 없음"
        elif row["first_order_day"] <= 6:
            return "7일 내 첫주문"
        else:
            return "8~29일 첫주문"
    cust2["activation_group"] = cust2.apply(group, axis=1)
    tbl = cust2.groupby("activation_group").agg(인원=("churn_yn", "size"), 이탈자=("churn_yn", lambda s: (s == "Y").sum()))
    tbl["이탈률(%)"] = (tbl["이탈자"] / tbl["인원"] * 100).round(1)
    print("[활성화 패턴] 첫주문 시점별 이탈률")
    print(tbl)
    print("(30명 미만 그룹 여부:", (tbl["인원"] < 30).to_dict(), ")")

    ref_counts = ref["referrer_customer_id"].value_counts()
    cust2["referral_count"] = cust2.index.map(ref_counts).fillna(0)
    cust2["referral_group"] = cust2["referral_count"].apply(lambda x: "2건 이상" if x >= 2 else ("1건" if x == 1 else "추천 안 함"))
    tbl2 = cust2.groupby("referral_group").agg(인원=("churn_yn", "size"), 이탈자=("churn_yn", lambda s: (s == "Y").sum()))
    tbl2["이탈률(%)"] = (tbl2["이탈자"] / tbl2["인원"] * 100).round(1)
    print("\n[추천 패턴] 추천 건수별 이탈률")
    print(tbl2)
    print("(30명 미만 그룹 여부:", (tbl2["인원"] < 30).to_dict(), ") — 이 패턴은 표본이 작아 참고용")

    section("4. 현실성 점검")
    print("acquisition_cost 채널별 평균:")
    print(acq.groupby("acquisition_channel")["acquisition_cost"].mean().round(0))
    days = (ref.dropna(subset=["reward_paid_date"])["reward_paid_date"] - ref.dropna(subset=["reward_paid_date"])["referral_date"]).dt.days
    print(f"\n추천 보상 지급 소요일: min={days.min()} max={days.max()} mean={days.mean():.1f} median={days.median()}")
    print(f"분산 0인 컬럼 여부(모든 값 동일) 체크:")
    for col, s in [("acquisition_cost", acq["acquisition_cost"]), ("reward_amount", ref["reward_amount"])]:
        print(f"  {col}: 고유값 {s.nunique()}개 (1개면 분산 없음)")

    section("5. 조인 검증")
    merged = pe.merge(cust[["customer_id"]], on="customer_id", how="left", indicator=True)
    loss = (merged["_merge"] != "both").sum()
    check("product_events -> customers 조인 손실 0건", loss == 0, f"{loss}건 손실")
    merged2 = ref.merge(cust[["customer_id"]], left_on="referred_customer_id", right_on="customer_id", how="left", indicator=True)
    loss2 = (merged2["_merge"] != "both").sum()
    check("referrals -> customers 조인 손실 0건", loss2 == 0, f"{loss2}건 손실")


if __name__ == "__main__":
    main()
