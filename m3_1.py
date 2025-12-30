# -*- coding: utf-8 -*-
# M3-1: Session State Manager

import streamlit as st
import pandas as pd
from m1 import DataManager

# --- 상수 정의 ---
SELECT_PLACEHOLDER = "- 선택 -"

def initialize_session_state():
    """
    세션 상태를 초기화합니다.
    앱이 시작될 때 한 번만 호출되어야 합니다.
    """
    # 데이터 매니저를 한 번만 초기화하여 세션 상태에 저장
    if 'm1' not in st.session_state:
        st.session_state.m1 = DataManager()
    
    defaults = {
        # 화면 제어
        'view_mode': 'landing',  # 'landing', 'user', 'admin'
        'logged_in': False,

        # 데이터
        'policy_db': st.session_state.m1.load_policy_data(),

        # 시뮬레이터 입력 값
        'predict_score': None,
        'current_score': 0.0,
        'target_kpi': SELECT_PLACEHOLDER,
        'rail_type': SELECT_PLACEHOLDER,
        'line_name': "",
        'start_station_input': "",
        'end_station_input': "",
        'line_section_input': "",
        'line_length_input': None,
        'input_val_1': None,
        'input_val_2': None,
        'input_minute': None,
        'future_input_val_1': None,
        'future_input_val_2': None,
        'future_input_minute': None,
        'target_year_input': None,
        'target_month_input': None,
        'future_goal_score_input': None,
        'future_goal_kpi_input': None,
        'goal_input_method': '성과지표',
        
        # UI 제어 플래그
        'use_current_elements_for_future': False,
        'predict_score_is_manual': False,
        'goal_input_by_user': True,

        # 시나리오 및 정책 편집
        'edited_policies_df': pd.DataFrame(),
        'uploaded_files': [],
        'loaded_scenario_name': None,
        'current_selected_modes': [],
        'future_selected_modes': [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # 데이터프레임들도 세션 시작 시 한 번만 초기화
    if 'physical_access_df' not in st.session_state:
        pai_access_modes = ['도보', '마을/시내버스', '광역버스', '지하철/광역철도', '승용차', '자전거', '택시', '공유PM']
        st.session_state.physical_access_df = pd.DataFrame({mode: [False] for mode in pai_access_modes})
    
    if 'future_physical_access_df' not in st.session_state:
        pai_access_modes = ['도보', '마을/시내버스', '광역버스', '지하철/광역철도', '승용차', '자전거', '택시', '공유PM']
        st.session_state.future_physical_access_df = pd.DataFrame({mode: [False] for mode in pai_access_modes})

    if 'tci_distance_df' not in st.session_state:
        tci_transfer_modes = ['대중교통', '도보', '승용차', '택시/배웅', 'PM']
        st.session_state.tci_distance_df = pd.DataFrame({mode: [0] for mode in tci_transfer_modes}, dtype=float)

    if 'future_tci_distance_df' not in st.session_state:
        tci_transfer_modes = ['대중교통', '도보', '승용차', '택시/배웅', 'PM']
        st.session_state.future_tci_distance_df = pd.DataFrame({mode: [0] for mode in tci_transfer_modes}, dtype=float)


def reset_user_inputs():
    """
    사용자 시뮬레이션 관련 입력을 모두 초기화합니다.
    페이지 뷰나 로그인 상태는 유지합니다.
    """
    m1 = DataManager()
    
    keys_to_reset = [
        'predict_score', 'current_score', 'target_kpi', 'rail_type',
        'line_name', 'start_station_input', 'end_station_input',
        'line_section_input', 'line_length_input', 'input_val_1', 'input_val_2',
        'input_minute', 'future_input_val_1', 'future_input_val_2',
        'future_input_minute', 'target_year_input', 'target_month_input',
        'future_goal_score_input', 'future_goal_kpi_input',
        'goal_input_method', 'use_current_elements_for_future',
        'predict_score_is_manual', 'goal_input_by_user',
        'edited_policies_df', 'loaded_scenario_name',
        'current_selected_modes', 'future_selected_modes'
    ]
    
    defaults = {
        'predict_score': None, 'current_score': 0.0, 'target_kpi': SELECT_PLACEHOLDER,
        'rail_type': SELECT_PLACEHOLDER, 'line_name': "", 'start_station_input': "",
        'end_station_input': "", 'line_section_input': "", 'line_length_input': None,
        'input_val_1': None, 'input_val_2': None, 'input_minute': None,
        'future_input_val_1': None, 'future_input_val_2': None, 'future_input_minute': None,
        'target_year_input': None, 'target_month_input': None, 'future_goal_score_input': None,
        'future_goal_kpi_input': None, 'goal_input_method': '성과지표',
        'use_current_elements_for_future': False, 'predict_score_is_manual': False,
        'goal_input_by_user': True, 'edited_policies_df': pd.DataFrame(), 'loaded_scenario_name': None,
        'current_selected_modes': [], 'future_selected_modes': []
    }

    for key in keys_to_reset:
        st.session_state[key] = defaults.get(key)

    pai_access_modes = ['도보', '마을/시내버스', '광역버스', '지하철/광역철도', '승용차', '자전거', '택시', '공유PM']
    st.session_state.physical_access_df = pd.DataFrame({mode: [False] for mode in pai_access_modes})
    st.session_state.future_physical_access_df = pd.DataFrame({mode: [False] for mode in pai_access_modes})

    tci_transfer_modes = ['대중교통', '도보', '승용차', '택시/배웅', 'PM']
    st.session_state.tci_distance_df = pd.DataFrame({mode: [0] for mode in tci_transfer_modes}, dtype=float)
    st.session_state.future_tci_distance_df = pd.DataFrame({mode: [0] for mode in tci_transfer_modes}, dtype=float)

    st.session_state.policy_db = m1.load_policy_data()

    st.toast("모든 사용자 입력이 초기화되었습니다.")