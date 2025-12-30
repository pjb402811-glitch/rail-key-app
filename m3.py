# -*- coding: utf-8 -*-
# M3: Main App (Router)
# 실행: streamlit run m3.py

import streamlit as st
import logging

# 모듈 임포트
from m3_1 import initialize_session_state

from m3_2 import draw_landing_page
from m3_3 import draw_user_view
from m3_4 import draw_admin_view

# --- 로깅 및 페이지 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
st.set_page_config(page_title="철도 정책 시뮬레이터", layout="wide")

# --- 세션 상태 초기화 ---
# 앱 실행 시 최초 1회만 호출
initialize_session_state()

# --- 메인 라우터 ---
def main():
    """
    st.session_state.view_mode에 따라 적절한 UI를 렌더링합니다.
    """
    view_mode = st.session_state.get('view_mode', 'landing')

    if view_mode == 'user':
        draw_user_view()
    elif view_mode == 'admin':
        draw_admin_view()
    else: # 'landing' or default
        draw_landing_page()

if __name__ == "__main__":
    main()