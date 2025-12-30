# -*- coding: utf-8 -*-
# M3-2: Landing Page View (Refined Design)

import streamlit as st
import base64
import os

# --- Helper to load local image as base64 ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

# --- 관리자 로그인 팝업 ---
@st.dialog("🔒 관리자 로그인")
def admin_login_popup():
    st.markdown("""
        <div style="margin-bottom: 20px; color: #555; font-size: 0.9em;">
            데이터 관리 및 시스템 설정을 위해 관리자 계정으로 로그인해주세요.
        </div>
    """, unsafe_allow_html=True)
    user_id = st.text_input("아이디 (ID)", placeholder="admin")
    password = st.text_input("비밀번호 (Password)", type="password", placeholder="admin")
    
    if st.button("로그인", use_container_width=True, type="primary"):
        if user_id == "admin" and password == "admin":
            st.session_state.logged_in = True
            st.session_state.view_mode = 'admin'
            st.rerun()
        else:
            st.error("⚠️ 아이디 또는 비밀번호가 일치하지 않습니다.")

def draw_landing_page():
    """배경화면과 사용자 중심 레이아웃이 적용된 랜딩 페이지"""
    
    # --- Background Image Logic ---
    bg_image_path = "railway_background.png"
    logo_path = "logo.jpg"
    
    # Use fallback URL if local file is missing
    bg_url = "https://images.unsplash.com/photo-1474487548417-781cb714c223?q=80&w=2070&auto=format&fit=crop"
    
    bg_style = ""
    if os.path.exists(bg_image_path):
        bin_str = get_base64_of_bin_file(bg_image_path)
        bg_style = f"""
            background-image: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.6)), url("data:image/png;base64,{bin_str}");
        """
    else:
        bg_style = f"""
            background-image: linear-gradient(rgba(0, 0, 0, 0.4), rgba(0, 0, 0, 0.6)), url("{bg_url}");
        """

    # --- Logo Logic ---
    logo_html = ""
    if os.path.exists(logo_path):
        logo_b64 = get_base64_of_bin_file(logo_path)
        logo_html = f"""
            <div style="position: fixed; bottom: 30px; right: 30px; z-index: 1000;">
                <img src="data:image/jpeg;base64,{logo_b64}" style="width: 200px; height: auto; opacity: 0.9;">
            </div>
        """

    # --- CSS Injection ---
    st.markdown(f"""
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        /* Global Font */
        html, body, [class*="css"] {{
            font-family: 'Pretendard', -apple-system, system-ui, sans-serif !important;
            color: #ffffff;
        }}

        /* Apply Background */
        .stApp {{
            {bg_style}
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        /* --- Admin Button Styling --- */
        div[data-testid="stElementContainer"]:has(#admin-marker) + div[data-testid="stElementContainer"] button {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: rgba(255, 255, 255, 0.8);
            font-size: 0.8rem;
            padding: 0.4rem 1.0rem;
            border-radius: 20px;
            backdrop-filter: blur(5px);
            float: right;
            transition: all 0.3s;
        }}
        div[data-testid="stElementContainer"]:has(#admin-marker) + div[data-testid="stElementContainer"] button:hover {{
            background: rgba(255, 255, 255, 0.3);
            color: #ffffff;
            border-color: #ffffff;
        }}

        /* --- Central Card Layout --- */
        .main-container {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            width: 80%;
            max-width: 900px;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(20px);
            border-radius: 30px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }}

        .hero-title {{
            font-size: 3.5rem;
            font-weight: 800;
            color: #ffffff;
            text-shadow: 0 4px 20px rgba(0,0,0,0.5);
            margin-bottom: 10px;
            letter-spacing: -0.02em;
        }}
        .hero-subtitle {{
            font-size: 1.2rem;
            font-weight: 400;
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 50px;
            letter-spacing: 0.05em;
        }}

        /* --- Start Button Styling (Refined) --- */
        /* Target the specific button using the marker */
        div[data-testid="stElementContainer"]:has(#user-marker) + div[data-testid="stElementContainer"] {{
            display: flex;
            justify-content: center;
        }}
        
        div[data-testid="stElementContainer"]:has(#user-marker) + div[data-testid="stElementContainer"] button {{
            width: 280px !important;
            height: 70px !important;
            background: linear-gradient(135deg, #007aff 0%, #0056b3 100%) !important;
            border: none !important;
            border-radius: 35px !important;
            box-shadow: 0 10px 30px rgba(0, 122, 255, 0.4) !important;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
            position: relative;
            overflow: hidden;
        }}
        
        div[data-testid="stElementContainer"]:has(#user-marker) + div[data-testid="stElementContainer"] button:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0, 122, 255, 0.6) !important;
            background: linear-gradient(135deg, #2b8fff 0%, #006cd9 100%) !important;
        }}

        div[data-testid="stElementContainer"]:has(#user-marker) + div[data-testid="stElementContainer"] button p {{
            font-size: 1.5rem !important;
            font-weight: 700 !important;
            color: #ffffff !important;
            letter-spacing: 1px;
        }}

        /* Hide Header/Footer */
        header {{visibility: hidden;}}
        footer {{visibility: hidden;}}
        
        /* Popup button reset */
        [data-testid="stDialog"] .stButton > button {{
            background: #203a43 !important;
            height: auto !important;
            width: 100% !important;
            box-shadow: none !important;
        }}
        
    </style>
    """, unsafe_allow_html=True)
    
    # --- HTML Structure ---
    
    # 1. Admin Button (Top Right)
    _, col_admin = st.columns([0.92, 0.08]) 
    with col_admin:
        st.markdown('<span id="admin-marker"></span>', unsafe_allow_html=True)
        if st.button("⚙️ Admin"): 
            admin_login_popup()

    # 2. Main Content (Centered manually via columns)
    st.markdown('<div style="height: 5vh;"></div>', unsafe_allow_html=True)
    
    _, center_col, _ = st.columns([1, 6, 1])
    
    with center_col:
        st.markdown("""
            <div style="
                padding: 60px 40px;
                background: rgba(0, 0, 0, 0.3);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.1);
                text-align: center;
                box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            ">
                <h1 style="
                    font-size: 3.2rem; 
                    font-weight: 800; 
                    margin-bottom: 10px; 
                    line-height: 1.3;
                    text-shadow: 0 2px 10px rgba(0,0,0,0.5);
                ">
                    국민만족도 기반<br>철도 정책과제 매칭 시스템
                </h1>
                <p style="
                    font-size: 1.1rem; 
                    color: rgba(255,255,255,0.7); 
                    margin-bottom: 50px; 
                    letter-spacing: 2px;
                ">
                    RAIL POLICY MATCHING SYSTEM
                </p>
        """, unsafe_allow_html=True)
        
        st.markdown('<span id="user-marker"></span>', unsafe_allow_html=True)
        if st.button("START"):
            st.session_state.view_mode = 'user'
            st.rerun()
            
        st.markdown("</div>", unsafe_allow_html=True) 

    # 3. Logo Injection
    st.markdown(logo_html, unsafe_allow_html=True)