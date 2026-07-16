# 이커머스 CS 데이터 미니 대시보드

모두의연구소 2주차 커리큘럼(Day1~Day4) 실습용 프로젝트. `raw/`의 데이터는 100% 가상(합성) 데이터입니다.
같은 분석 결과를 3가지 방식(Streamlit / Cloudflare Pages / Netlify)으로 배포해 비교합니다.

## 구성
- `raw/` — 이커머스 VOC·고객·상담·만족도·이용이력 CSV 5종
- `components/` — 분석 결과를 시각화하는 matplotlib 스크립트 (직접 실행 시 `components/output/`에 PNG 저장)
- `app.py` — Streamlit 4탭 대시보드 (컴포넌트 이미지 + 인사이트 요약)
- `requirements.txt` — streamlit, pandas, matplotlib
- `web/` — Cloudflare Pages·Netlify 배포용 정적 HTML/JS 대시보드
  - `build_data.py` — raw CSV를 읽어 `web/data.json`으로 미리 집계(정적 호스팅은 서버 재계산이 없으므로 빌드 시점에 구움)
  - `index.html` — Plotly.js로 그리는 인터랙티브 대시보드(다크모드 대응, 4탭)

## 로컬 실행
```
pip install -r requirements.txt
python components/01_voc_overview.py   # 등 각 컴포넌트 스크립트 실행
streamlit run app.py
```

### 정적 HTML 버전 로컬 확인
```
cd web
python build_data.py
python -m http.server 8000   # 이후 http://localhost:8000 접속
```

## 배포

### Streamlit Community Cloud
1. 이 폴더를 GitHub Public 저장소로 push (**필수** — Streamlit Cloud는 GitHub 저장소만 읽음)
2. share.streamlit.io에서 GitHub 계정 연동 후 New app으로 이 저장소 + `app.py` 선택 → Deploy

### Cloudflare Pages (wrangler CLI)
```
cd web
python build_data.py
wrangler login
wrangler pages deploy . --project-name=ecommerce-cs-dashboard
```

### Netlify (netlify-cli)
```
cd web
python build_data.py
netlify login
netlify deploy --dir=. --prod
```

두 정적 호스팅 모두 GitHub 저장소 연동 없이 CLI로 폴더를 직접 올릴 수 있습니다(단, `data.json`을 미리 빌드해둬야 함).
