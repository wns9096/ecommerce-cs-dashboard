import streamlit as st
import glob

st.title("CS 데이터 미니 대시보드 (배포 테스트)")

for path in sorted(glob.glob("components/output/*.png")):
    st.image(path)
