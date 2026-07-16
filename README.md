# 이커머스 CS 데이터 미니 대시보드

모두의연구소 2주차 커리큘럼(Day1~Day3) 실습용 프로젝트. `raw/`의 데이터는 100% 가상(합성) 데이터입니다.

## 구성
- `raw/` — 이커머스 VOC·고객·상담·만족도·이용이력 CSV 5종
- `components/` — 분석 결과를 시각화하는 matplotlib 스크립트 (직접 실행 시 `components/output/`에 PNG 저장)
- `app.py` — Streamlit 미니 대시보드 (컴포넌트 이미지 나열)
- `requirements.txt` — streamlit, pandas, matplotlib

## 로컬 실행
```
pip install -r requirements.txt
python components/01_voc_overview.py   # 등 각 컴포넌트 스크립트 실행
streamlit run app.py
```

## 배포 (Streamlit Community Cloud)
1. 이 폴더를 GitHub Public 저장소로 push
2. share.streamlit.io에서 GitHub 계정 연동 후 New app으로 이 저장소 + `app.py` 선택 → Deploy
