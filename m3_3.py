# -*- coding: utf-8 -*-
# M3-3: User View (일반 사용자 화면)
# pyinstaller --noconfirm RailIndicatorApp.spec

import streamlit as st
import pandas as pd
import altair as alt
import re
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta
import os
import tempfile
import numpy as np
import vl_convert as vlc

# 모듈 임포트
from m1 import DataManager, resource_path
from m2 import SatisfactionCalculator, calculate_physical_tai, calculate_physical_eai, calculate_pai, calculate_tci_score
from m4 import ProjectRecommender
from m5 import PdfGenerator
from m3_1 import reset_user_inputs, SELECT_PLACEHOLDER

def draw_user_view():
    """일반 사용자용 시뮬레이터 페이지를 그립니다."""

    # --- 모델 및 데이터 로더 초기화 ---
    m1_instance = DataManager()
    config, pai_coeffs, tci_coeffs = m1_instance.load_coefficients()
    m2 = SatisfactionCalculator(config)
    m4 = ProjectRecommender()
    m5 = PdfGenerator()
    KPI_ABBREVIATIONS = m1_instance.KPI_ABBREVIATIONS

    # --- 콜백 함수 ---
    def reset_manual_flag():
        st.session_state.predict_score_is_manual = False

    def handle_manual_predict_score_change():
        st.session_state.predict_score_is_manual = True

    def copy_current_to_future():
        if st.session_state.use_current_elements_for_future:
            # 기존 값 복사
            st.session_state.future_input_val_1 = st.session_state.input_val_1
            st.session_state.future_input_val_2 = st.session_state.input_val_2
            st.session_state.future_input_minute = st.session_state.input_minute
            
            # PAI/TCI 데이터프레임 복사
            if 'physical_access_df' in st.session_state:
                st.session_state.future_physical_access_df = st.session_state.physical_access_df.copy()
            if 'tci_combined_df' in st.session_state: # 기존 tci_combined_df가 있다면 복사
                st.session_state.future_tci_combined_df = st.session_state.tci_combined_df.copy()

        else:
            # 기존 값 초기화
            st.session_state.future_input_val_1 = None
            st.session_state.future_input_val_2 = None
            st.session_state.future_input_minute = None

            # PAI/TCI 데이터프레임 초기화
            rail_type = st.session_state.get('rail_type', SELECT_PLACEHOLDER)
            all_modes = ['도보', '마을/시내버스', '광역버스', '지하철/광역철도', '승용차', '자전거', '택시', '공유PM']
            if rail_type == '광역철도':
                pai_access_modes = [mode for mode in all_modes if mode != '지하철/광역철도']
            else:
                pai_access_modes = all_modes
            
            st.session_state.future_physical_access_df = pd.DataFrame(
                {mode: [False] for mode in pai_access_modes}
            )
            # TCI DataFrame 초기화 (모든 모드 선택 및 거리 0)
            initial_data = []
            for mode in DataManager.TCI_ALL_MODES:
                initial_data.append({'Mode': mode, 'Selected': True, 'Distance': 0.0})
            st.session_state.future_tci_combined_df = pd.DataFrame(initial_data)
        reset_manual_flag()

    def update_goal_kpi_from_score():
        if st.session_state.goal_input_method == '만족도':
            st.session_state.goal_input_by_user = True
            rail_type = st.session_state.rail_type
            target_kpi = st.session_state.target_kpi
            score = st.session_state.future_goal_score_input

            if score is not None and rail_type != SELECT_PLACEHOLDER and target_kpi != SELECT_PLACEHOLDER:
                if target_kpi == "환승시설 편의성":
                    st.session_state.future_goal_kpi_input = score
                else:
                    abbreviated_kpi = KPI_ABBREVIATIONS.get(target_kpi, target_kpi)
                    kpi_val = m2.reverse_calculate_value(rail_type, abbreviated_kpi, score)
                    st.session_state.future_goal_kpi_input = kpi_val

    def update_goal_score_from_kpi():
        if st.session_state.goal_input_method == '성과지표':
            st.session_state.goal_input_by_user = True
            rail_type = st.session_state.rail_type
            target_kpi = st.session_state.target_kpi
            kpi_val = st.session_state.future_goal_kpi_input

            if kpi_val is not None and rail_type != SELECT_PLACEHOLDER and target_kpi != SELECT_PLACEHOLDER:
                if target_kpi == "환승시설 편의성":
                    st.session_state.future_goal_score_input = kpi_val
                else:
                    abbreviated_kpi = KPI_ABBREVIATIONS.get(target_kpi, target_kpi)
                    kpi_val_safe = kpi_val if kpi_val is not None else 0.0
                    score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, kpi_val_safe)
                    st.session_state.future_goal_score_input = score

    # --- 데이터 저장/불러오기 함수 ---
    def sanitize_filename(name):
        return re.sub(r'[\\/*?:\"<>|]', "_", name) if name else ""

    def convert_value(value):
        if value in ['None', 'nan', ''] or pd.isna(value):
            return None
        try:
            float_val = float(value)
            return int(float_val) if float_val.is_integer() else float_val
        except (ValueError, TypeError):
            if str(value).lower() == 'true': return True
            if str(value).lower() == 'false': return False
            return value

    def get_scenario_as_csv_string():
        keys_to_save = ['target_kpi', 'rail_type', 'line_name', 'station_name_input', 'start_station_input', 'end_station_input', 'line_section_input', 'line_length_input', 'input_val_1', 'input_val_2', 'input_minute', 'future_input_val_1', 'future_input_val_2', 'future_input_minute', 'target_year_input', 'target_month_input', 'future_goal_score_input', 'predict_score', 'goal_input_method', 'use_current_elements_for_future']
        state_to_save = {key: st.session_state.get(key) for key in keys_to_save}
        if 'edited_policies_df' in st.session_state and 'active' in st.session_state.edited_policies_df.columns:
            active_projects = st.session_state.edited_policies_df[st.session_state.edited_policies_df['active']]
            state_to_save['active_policy_names'] = ','.join(active_projects['name'].tolist())
        df_to_save = pd.DataFrame(state_to_save.items(), columns=['key', 'value'])
        output = io.BytesIO()
        df_to_save.to_csv(output, index=False, encoding='utf-8-sig')
        return output.getvalue()

    def load_state_from_uploaded_file(uploaded_file):
        if uploaded_file is None: return
        try:
            df = pd.read_csv(uploaded_file).fillna('')
            for _, row in df.iterrows():
                key, value = row['key'], row['value']
                if key == 'active_policy_names' and value:
                    st.session_state['loaded_active_names'] = str(value).split(',')
                else:
                    st.session_state[key] = convert_value(value)
            st.session_state.loaded_scenario_name = uploaded_file.name
            st.toast(f"✅ 시나리오 '{uploaded_file.name}'를 불러왔습니다.")
        except Exception as e:
            st.error(f"🚨 파일 처리 중 오류 발생: {e}")

    def process_uploaded_scenario():
        uploaded_files = st.session_state.get("scenario_multi_uploader")
        if uploaded_files:
            last_file = uploaded_files[-1]
            reset_user_inputs()
            load_state_from_uploaded_file(last_file)

    # --- 사용 안내 팝업 ---
    @st.dialog("프로그램 사용 안내")
    def show_guide_popup():
        st.write("프로그램의 주요 기능, 사용법, 데이터 구조 등에 대한 설명이 포함된 문서입니다.")
        st.write("아래 버튼을 클릭하여 프로그램 설명서 파일을 다운로드하세요.")
        with open(resource_path("data/docs/프로그램 설명서_v1.pdf"), "rb") as fp:
            st.download_button("프로그램 설명서.pdf 다운로드", fp, "프로그램 설명서_v1.pdf", "application/pdf", use_container_width=True)

    # --- UI 렌더링 (헤더) ---
    title_col, home_button_col, info_button_col = st.columns([0.7, 0.15, 0.15])
    with title_col:
        st.title("🚄 국민만족도 기반 철도 정책과제 매칭 시스템")
    with home_button_col:
        if st.button("🏠 초기 화면으로 돌아가기", use_container_width=True):
            st.session_state.view_mode = 'landing'
            st.rerun()
    with info_button_col:
        if st.button("ℹ️ 사용 안내", use_container_width=True):
            show_guide_popup()

    # --- 스타일 ---
    # --- Professional Style Injection ---
    st.markdown("""
    <style>
        @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

        /* Global Font Settings */
        html, body, [class*="css"] {
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif;
            color: #333333;
        }

        /* Header Boxes with Gradients and Shadows */
        .header-box {
            padding: 16px 24px;
            border-radius: 12px;
            margin-bottom: 24px;
            font-weight: 700;
            font-size: 1.25rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            display: flex;
            align-items: center;
            letter-spacing: -0.02em;
        }

        .blue-box {
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            color: #0d47a1;
            border-left: 6px solid #1565c0;
        }

        .green-box {
            background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
            color: #1b5e20;
            border-left: 6px solid #2e7d32;
        }

        .purple-box {
            background: linear-gradient(135deg, #f3e5f5 0%, #e1bee7 100%);
            color: #4a148c;
            border-left: 6px solid #7b1fa2;
        }

        /* Input Fields Styling */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input {
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            padding: 10px;
            transition: all 0.3s ease;
        }
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus {
            border-color: #1565c0;
            box-shadow: 0 0 0 2px rgba(21, 101, 192, 0.2);
        }

        /* Button Styling */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }

        /* Metric Styling */
        [data-testid="stMetricValue"] {
            font-size: 1.6rem !important;
            font-weight: 800;
            color: #2c3e50;
        }
        [data-testid="stMetricLabel"] {
            font-size: 0.9rem !important;
            color: #7f8c8d;
            font-weight: 500;
        }

        /* Main Container Adjustments */
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            gap: 1.5rem;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # --- UI 변수 초기화 ---
    is_fail = False
    current_val, current_score = 0.0, 0.0
    future_predict_val, future_predict_score = 0.0, 0.0
    future_goal_val, future_goal_score = 0.0, 0.0
    unit = ""
    sens_df = pd.DataFrame({'성과 지표 값': [], '만족도 점수': []})
    target_year, target_month = datetime.now().year + 5, 12

    # ==============================================================================
    # PART 1: 현재 철도 현황
    # ==============================================================================
    top_col1, top_col2 = st.columns(2)

    with top_col1:
        with st.container(border=True):
            st.markdown('<div class="header-box blue-box">1. 현재 철도 현황</div>', unsafe_allow_html=True)
            st.write("가. 분석할 **성과지표**와 **철도 유형**을 선택하고, 분석할 **철도 노선 정보**를 입력해주세요.")

            kpi_col, type_col = st.columns(2)
            with kpi_col:
                kpi_options = [SELECT_PLACEHOLDER, "물리적 접근성", "시간적 접근성", "경제적 접근성", "운행횟수", 
                            "표정속도", "열차운행 정시성", "환승시설 편의성", "역사 시설 쾌적성", 
                            "열차이용 쾌적성", "환승시설 쾌적성"]
                st.selectbox("분석할 성과지표", kpi_options, key='target_kpi')
            with type_col:
                rail_type_options = [SELECT_PLACEHOLDER, "고속철도", "일반철도", "광역철도"]
                st.selectbox("철도 유형", rail_type_options, key='rail_type')

            # KPI에 따라 철도 노선/역 정보 입력 UI를 동적으로 변경
            station_info_kpis = ["물리적 접근성", "시간적 접근성", "환승시설 편의성", "역사 시설 쾌적성", "환승시설 쾌적성"]
            target_kpi = st.session_state.get('target_kpi', SELECT_PLACEHOLDER)

            if target_kpi in station_info_kpis:
                # --- 역 정보 입력 UI ---
                st.session_state.start_station_input = ""
                st.session_state.end_station_input = ""
                st.session_state.line_length_input = None
                st.session_state.line_section_input = ""
                
                line_info_col, station_info_col = st.columns(2)
                with line_info_col:
                    st.text_input("노선명", placeholder="예: 경부고속선", key='line_name')
                with station_info_col:
                    st.text_input("역명", placeholder="예: 서울역", key='station_name_input')
            else:
                # --- 노선 정보 입력 UI ---
                st.session_state.station_name_input = ""

                line_info, start_station_col, tilde_col, end_station_col, line_length = st.columns([2, 1, 0.2, 1, 2])
                with line_info:
                    st.text_input("노선명", placeholder="예: 경부고속선", key='line_name')
                with start_station_col:
                    st.text_input("시점역", placeholder="예: 서울", key='start_station_input')
                with tilde_col:
                    st.markdown("<p style='text-align: center; margin-top: 28px;'>~</p>", unsafe_allow_html=True)
                with end_station_col:
                    st.text_input("종점역", placeholder="예: 부산", key='end_station_input')
                with line_length:
                    st.number_input("노선 길이 (km)", min_value=0.0, step=1.0, placeholder="예: 423.9", key='line_length_input')


            if st.session_state.start_station_input and st.session_state.end_station_input:
                st.session_state.line_section_input = f"{st.session_state.start_station_input}~{st.session_state.end_station_input}"
            else:
                st.session_state.line_section_input = ""

            st.write("나. 성과지표 분석을 위해 다음 항목을 입력해주세요.")
            
            target_kpi = st.session_state.target_kpi
            rail_type = st.session_state.rail_type

            if target_kpi == "물리적 접근성":
                unit = "점"
                st.write("역으로 접근 가능한 교통수단을 선택해주세요.(중복 가능)")
                
                all_modes = ['도보', '마을/시내버스', '광역버스', '지하철/광역철도', '승용차', '자전거', '택시', '공유PM']
                if rail_type == '광역철도':
                    pai_access_modes = [mode for mode in all_modes if mode != '지하철/광역철도']
                else:
                    pai_access_modes = all_modes

                current_df = st.session_state.physical_access_df
                new_data = {mode: [current_df.get(mode, [False])[0]] for mode in pai_access_modes}
                st.session_state.physical_access_df = pd.DataFrame(new_data)
                
                st.session_state.physical_access_df = st.data_editor(
                    st.session_state.physical_access_df,
                    column_config={mode: st.column_config.CheckboxColumn(mode, default=False) for mode in pai_access_modes},
                    hide_index=True,
                    use_container_width=True,
                    key="current_pai_editor"
                )

            elif target_kpi == "시간적 접근성":
                c1, _, _ = st.columns(3)
                c1.number_input("철도역 접근 소요시간(분)", step=10, placeholder="예: 30", key='input_val_1')
                unit = "분"  # [수정] 원래 "점"이었던 것을 "분"으로 변경 (이제 지표 자체가 시간이니까요)
            elif target_kpi == "경제적 접근성":
                c1, c2, c3 = st.columns(3)
                c1.number_input("접근 비용(원)", step=100, placeholder="예: 2500", key='input_val_1')
                c2.number_input("철도 비용(원)", step=100, placeholder="예: 59800", key='input_val_2')
                c3.number_input("주차 비용(원)", step=100, placeholder="예: 15000", key='input_val_3')
                unit = "원"
            elif target_kpi == "운행횟수":
                c1, _, _ = st.columns(3)
                c1.number_input("운행횟수 (회/일)", step=1, placeholder="예: 150", key='input_val_1')
                unit = "회/일"
            elif target_kpi == "표정속도":
                c1, c2, _ = st.columns(3)
                c1.number_input("운행거리 (km)", step=1.0, placeholder="예: 400", key='input_val_1')
                c2.number_input("소요시간 (분)", step=1, min_value=0, placeholder="예: 150", key='input_minute')
                unit = "km/h"
                if st.session_state.get('input_minute') is not None:
                    st.session_state.input_val_2 = st.session_state.input_minute / 60.0
            elif target_kpi == "열차운행 정시성":
                c1, _, _ = st.columns(3)
                c1.number_input("정시운행률 (%)", step=0.1, placeholder="예: 90.5", key='input_val_1')
                unit = "%"
            elif target_kpi == "환승시설 편의성":
                unit = "점"
                st.write("각 환승 수단별 환승 거리를 미터(m) 단위로 입력하세요.")
                
                # TCI 데이터프레임 초기화 또는 업데이트
                if 'tci_combined_df' not in st.session_state:
                    initial_data = []
                    for mode in DataManager.TCI_ALL_MODES:
                        initial_data.append({'Mode': mode, 'Selected': True, 'Distance': 0.0}) # 기본값은 모두 선택됨
                    st.session_state.tci_combined_df = pd.DataFrame(initial_data)
                
                # data_editor를 통해 선택 및 거리 입력
                edited_tci_df = st.data_editor(                        st.session_state.tci_combined_df,
                column_config={
                "Mode": st.column_config.Column("환승 수단", disabled=True),
                "Selected": st.column_config.CheckboxColumn("선택", default=True),
                "Distance": st.column_config.NumberColumn("거리(m)", min_value=0.0, format="%d m")
                },
                hide_index=True,
                use_container_width=True,
                key="current_tci_editor"
                )
                st.session_state.tci_combined_df = edited_tci_df.copy() # 세션 상태 업데이트

                # 선택된 모드만 필터링하여 distances 딕셔너리 생성
                distances = {row['Mode']: row['Distance'] for idx, row in edited_tci_df.iterrows() if row['Selected']}
                st.session_state.current_tci_distances = distances
            elif target_kpi == "역사 시설 쾌적성":
                c1, c2, _ = st.columns(3)
                unit = "명/㎡"
                placeholders = {"고속철도": ("예 : 10,000", "직접 수정하세요"), "일반철도": ("예 : 3,000", "예 : 300"), "광역철도": ("예 : 3,000", "예 : 300")}
                ph1, ph2 = placeholders.get(rail_type, (None, None))
                c1.number_input("승하차인원 (명/시간)", step=1, placeholder=ph1, key='input_val_1')
                c2.number_input("승강장 면적(㎡)", step=1, placeholder=ph2, key='input_val_2')
            elif target_kpi == "열차이용 쾌적성":
                c1, c2, _ = st.columns(3)
                unit = "%"
                placeholders = {"고속철도": ("예 : 65", "예 : 60"), "일반철도": ("예 : 60", "예 : 72"), "광역철도": ("예 : 200", "예 : 160")}
                ph1, ph2 = placeholders.get(rail_type, (None, None))
                c1.number_input("재차인원 (명)", step=1, placeholder=ph1, key='input_val_1')
                c2.number_input("공급량 (명)", step=1, placeholder=ph2, key='input_val_2')
            elif target_kpi == "환승시설 쾌적성":
                c1, c2, _ = st.columns(3)
                unit = "명/㎡"
                c1.number_input("승하차인원 (명)", step=1, placeholder="예 : 10,000", key='input_val_1')
                c2.number_input("환승통로 면적(㎡)", placeholder="직접 수정하세요", key='input_val_2')

            kpis_with_one_input = ["운행횟수", "열차운행 정시성", "시간적 접근성"]
            kpis_with_three_inputs = ["경제적 접근성"]
            kpis_with_df_input = ["물리적 접근성", "환승시설 편의성"]
            base_inputs_valid = (target_kpi != SELECT_PLACEHOLDER) and (rail_type != SELECT_PLACEHOLDER)
            val1 = st.session_state.get('input_val_1')
            val2 = st.session_state.get('input_val_2')
            val3 = st.session_state.get('input_val_3')
            
            inputs_are_valid = base_inputs_valid
            if target_kpi in kpis_with_df_input:
                inputs_are_valid = base_inputs_valid
            elif target_kpi in kpis_with_three_inputs:
                inputs_are_valid = inputs_are_valid and (val1 is not None) and (val2 is not None) and (val3 is not None)
            elif target_kpi not in kpis_with_one_input:
                 inputs_are_valid = inputs_are_valid and (val1 is not None) and (val2 is not None)
            elif target_kpi in kpis_with_one_input:
                inputs_are_valid = inputs_are_valid and (val1 is not None)

            if inputs_are_valid:
                abbreviated_kpi = KPI_ABBREVIATIONS.get(target_kpi, target_kpi)

                if target_kpi == "물리적 접근성":
                    st.session_state.current_selected_modes = [mode for mode, is_selected in st.session_state.physical_access_df.iloc[0].items() if is_selected]
                    if any(st.session_state.current_selected_modes):
                        weights = pai_coeffs.get('weights', {}).get(rail_type, {})
                        alpha = pai_coeffs.get('alpha', {}).get(rail_type, 0)
                        current_val = calculate_pai(st.session_state.current_selected_modes, weights, alpha)
                        current_val_safe = current_val if current_val is not None else 0.0
                        current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                    else:
                        current_val, current_score = 0.0, 0.0
                        st.session_state.current_selected_modes = [] # Clear the PAI specific selected modes
                elif target_kpi == "시간적 접근성":
                    current_val = val1  # [핵심] 5분이면 그냥 5를 가집니다.
                    current_val_safe = current_val if current_val is not None else 0.0
                    # 이제 만족도 계산기에 '5'가 들어갑니다 -> 정상 계산됨
                    current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                elif target_kpi == "경제적 접근성":
                    current_val = calculate_physical_eai(val1, val2, val3)
                    current_val_safe = current_val if current_val is not None else 0.0
                    current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                elif target_kpi == "표정속도":
                    current_val = (val1 / val2) if val2 > 0 else 0
                    current_val_safe = current_val if current_val is not None else 0.0
                    current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                elif target_kpi == "환승시설 편의성":
                    tci_distances = st.session_state.get('current_tci_distances', {}) 
                    if any(d > 0 for d in tci_distances.values()):
                        rail_type_coeffs = tci_coeffs.get(rail_type, {})
                        s_max = tci_coeffs.get('S_max', 10.0)
                        current_score = calculate_tci_score(tci_distances, rail_type_coeffs, s_max)
                        current_val = current_score
                    else:
                        current_val, current_score = 0.0, 0.0                
                elif target_kpi in ["열차이용 쾌적성"]:
                    current_val = (val1 / val2) * 100 if val2 > 0 else 0
                    current_val_safe = current_val if current_val is not None else 0.0
                    current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                elif target_kpi in ["역사 시설 쾌적성", "환승시설 쾌적성"]:
                    current_val = (val1 / val2) if val2 > 0 else 0
                    current_val_safe = current_val if current_val is not None else 0.0
                    current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                else: # Default case for other KPIs
                    current_val = val1
                    current_val_safe = current_val if current_val is not None else 0.0
                    current_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, current_val_safe)
                    st.session_state.current_score = current_score

            if current_val > 0 and target_kpi != "환승시설 편의성":
                # 변환 없이 current_val 그대로 사용
                sens_df = m2.generate_sensitivity_table(rail_type, target_kpi, current_val)
                if not sens_df.empty:
                    # 단위도 원래대로 '원'(unit) 사용
                    sens_df.index = [f"{target_kpi} ({unit})", "만족도"]

            st.write(f"다. 현재 **{target_kpi}**({current_val:.2f}{unit})에 따른 국민 만족도는 **{current_score:.2f}점** (10점 만점) 입니다.")
            st.dataframe(sens_df, use_container_width=True)


    # ==============================================================================
    # PART 2: 미래 철도 상황
    # ==============================================================================

    with top_col2:
        with st.container(border=True):
            st.markdown('<div class="header-box green-box">2. 미래 철도 상황</div>', unsafe_allow_html=True)
            kpi_display_name = f"'{target_kpi}'" if target_kpi != SELECT_PLACEHOLDER else "성과지표"
            st.write(f"가. 철도 환경 변화에 따른 **{kpi_display_name}의 장래 목표연도**를 입력해 주세요.")
            date_col1, date_col2 = st.columns(2)
            with date_col1:
                st.number_input("목표 연도", placeholder=f"예: {datetime.now().year + 5}", step=1, key='target_year_input')
            with date_col2:
                st.number_input("목표 월", placeholder="예: 12", min_value=1, max_value=12, step=1, key='target_month_input')
            
            predict_score_placeholder = f"예: {min(10, st.session_state.current_score * 1.1):.1f}" if inputs_are_valid else None
            goal_score_placeholder = f"예: {min(10, st.session_state.current_score * 1.2):.1f}" if inputs_are_valid else None

            st.write(f"나. 철도 환경 변화에 장래 **{kpi_display_name} 관련 요소**를 입력해주세요.")
            
            is_disabled = st.session_state.use_current_elements_for_future
            
            if target_kpi == "물리적 접근성":
                st.write("장래에 역으로 접근 가능한 교통수단을 선택해주세요.(중복 가능)")
                all_modes = ['도보', '마을/시내버스', '광역버스', '지하철/광역철도', '승용차', '자전거', '택시', '공유PM']
                if rail_type == '광역철도':
                    pai_access_modes = [mode for mode in all_modes if mode != '지하철/광역철도']
                else:
                    pai_access_modes = all_modes
                
                future_df = st.session_state.future_physical_access_df
                new_data = {mode: [future_df.get(mode, [False])[0]] for mode in pai_access_modes}
                st.session_state.future_physical_access_df = pd.DataFrame(new_data)

                st.session_state.future_physical_access_df = st.data_editor(
                    st.session_state.future_physical_access_df,
                    column_config={mode: st.column_config.CheckboxColumn(mode, default=False) for mode in pai_access_modes},
                    hide_index=True,
                    use_container_width=True,
                    key="future_pai_editor",
                    disabled=is_disabled
                )
            elif target_kpi == "시간적 접근성":
                c1_future, _, _ = st.columns(3)
                c1_future.number_input("철도역 접근 소요시간(분)", step=10, placeholder="예: 15", key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "경제적 접근성":
                c1_future, c2_future, c3_future = st.columns(3)
                c1_future.number_input("접근 비용(원)", step=100, placeholder="예: 2500", key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
                c2_future.number_input("철도 비용(원)", step=100, placeholder="예: 59800", key='future_input_val_2', on_change=reset_manual_flag, disabled=is_disabled)
                c3_future.number_input("주차 비용(원)", step=100, placeholder="예: 15000", key='future_input_val_3', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "운행횟수":
                c1_future, _, _ = st.columns(3)
                c1_future.number_input("운행횟수 (회/일)", step=1, placeholder="예: 150", key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "표정속도":
                c1_future, c2_future, _ = st.columns(3)
                c1_future.number_input("운행거리 (km)", step=1.0, placeholder="예: 400", key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
                c2_future.number_input("소요시간 (분)", step=1, min_value=0, placeholder="예: 150", key='future_input_minute', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "열차운행 정시성":
                c1_future, _, _ = st.columns(3)
                c1_future.number_input("정시운행률 (%)", step=0.1, placeholder="예: 90.5", key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "환승시설 편의성":
                st.write("각 환승 수단별 장래 환승 거리를 미터(m) 단위로 입력하세요.")
                
                # TCI 데이터프레임 초기화 또는 업데이트
                if 'future_tci_combined_df' not in st.session_state:
                    initial_data = []
                    for mode in DataManager.TCI_ALL_MODES:
                        initial_data.append({'Mode': mode, 'Selected': True, 'Distance': 0.0}) # 기본값은 모두 선택됨
                    st.session_state.future_tci_combined_df = pd.DataFrame(initial_data)

                # data_editor를 통해 선택 및 거리 입력
                edited_future_tci_df = st.data_editor(
                    st.session_state.future_tci_combined_df,
                    column_config={
                        "Mode": st.column_config.Column("환승 수단", disabled=True),
                        "Selected": st.column_config.CheckboxColumn("선택", default=True),
                        "Distance": st.column_config.NumberColumn("거리(m)", min_value=0.0, format="%d m")
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="future_tci_editor",
                    disabled=is_disabled
                )
                st.session_state.future_tci_combined_df = edited_future_tci_df.copy() # 세션 상태 업데이트

                # 선택된 모드만 필터링하여 distances 딕셔너리 생성
                distances = {row['Mode']: row['Distance'] for idx, row in edited_future_tci_df.iterrows() if row['Selected']}
                st.session_state.future_tci_distances = distances
            elif target_kpi == "역사 시설 쾌적성":
                c1_future, c2_future, _ = st.columns(3)
                placeholders = {"고속철도": ("예 : 10,000", "직접 수정하세요"), "일반철도": ("예 : 3,000", "예 : 300"), "광역철도": ("예 : 3,000", "예 : 300")}
                ph1, ph2 = placeholders.get(rail_type, (None, None))
                c1_future.number_input("승하차인원 (명/시간)", step=1, placeholder=ph1, key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
                c2_future.number_input("승강장 면적(㎡)", step=1, placeholder=ph2, key='future_input_val_2', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "열차이용 쾌적성":
                c1_future, c2_future, _ = st.columns(3)
                placeholders = {"고속철도": ("예 : 65", "예 : 60"), "일반철도": ("예 : 60", "예 : 72"), "광역철도": ("예 : 200", "예 : 160")}
                ph1, ph2 = placeholders.get(rail_type, (None, None))
                c1_future.number_input("재차인원 (명)", step=1, placeholder=ph1, key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
                c2_future.number_input("공급량 (명)", step=1, placeholder=ph2, key='future_input_val_2', on_change=reset_manual_flag, disabled=is_disabled)
            elif target_kpi == "환승시설 쾌적성":
                c1_future, c2_future, _ = st.columns(3)
                c1_future.number_input("승하차인원 (명)", step=1, placeholder="예 : 10,000", key='future_input_val_1', on_change=reset_manual_flag, disabled=is_disabled)
                c2_future.number_input("환승통로 면적(㎡)", placeholder="직접 수정하세요", key='future_input_val_2', on_change=reset_manual_flag, disabled=is_disabled)

            st.checkbox("현재 요소 및 만족도와 동일하게 설정", key="use_current_elements_for_future", on_change=copy_current_to_future, disabled=not inputs_are_valid)
            
            calculated_predict_score = None
            future_val1 = st.session_state.get('future_input_val_1')
            future_val2 = st.session_state.get('future_input_val_2')
            future_val3 = st.session_state.get('future_input_val_3')

            if target_kpi == "표정속도":
                if st.session_state.get('future_input_minute') is not None:
                    st.session_state.future_input_val_2 = st.session_state.future_input_minute / 60.0
                    future_val2 = st.session_state.future_input_val_2
            
            future_inputs_are_valid = base_inputs_valid
            if target_kpi in kpis_with_df_input:
                future_inputs_are_valid = base_inputs_valid
            elif target_kpi in kpis_with_three_inputs:
                future_inputs_are_valid = future_inputs_are_valid and (future_val1 is not None) and (future_val2 is not None) and (future_val3 is not None)
            elif not (target_kpi in kpis_with_one_input):
                future_inputs_are_valid = future_inputs_are_valid and (future_val1 is not None) and (future_val2 is not None)

            if future_inputs_are_valid:
                future_kpi_val = 0
                abbreviated_kpi = KPI_ABBREVIATIONS.get(target_kpi, target_kpi)

                if target_kpi == "물리적 접근성":
                    st.session_state.future_selected_modes = [mode for mode, is_selected in st.session_state.future_physical_access_df.iloc[0].items() if is_selected]
                    if any(st.session_state.future_selected_modes):
                        weights = pai_coeffs.get('weights', {}).get(rail_type, {})
                        alpha = pai_coeffs.get('alpha', {}).get(rail_type, 0)
                        future_kpi_val = calculate_pai(st.session_state.future_selected_modes, weights, alpha)
                        future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                        calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
                    else:
                        future_kpi_val, calculated_predict_score = 0.0, 0.0
                elif target_kpi == "시간적 접근성":
                    st.session_state.future_selected_modes = [] 
                    future_kpi_val = future_val1  # [핵심] 입력된 미래 시간(분)을 그대로 사용
                    future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                    calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
                elif target_kpi == "경제적 접근성":
                    st.session_state.future_selected_modes = [] 
                    future_kpi_val = calculate_physical_eai(future_val1, future_val2, future_val3)
                    future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                    calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
                elif target_kpi == "표정속도":
                    st.session_state.future_selected_modes = [] # Clear PAI-specific modes
                    future_kpi_val = (future_val1 / future_val2) if future_val2 > 0 else 0
                    future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                    calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
                elif target_kpi == "환승시설 편의성":
                    tci_distances = st.session_state.get('future_tci_distances', {})
                    if any(d > 0 for d in tci_distances.values()):
                        rail_type_coeffs = tci_coeffs.get(rail_type, {})
                        s_max = tci_coeffs.get('S_max', 10.0)
                        calculated_predict_score = calculate_tci_score(tci_distances, rail_type_coeffs, s_max)
                        future_kpi_val = calculated_predict_score 
                    else:
                        future_kpi_val, calculated_predict_score = 0.0, 0.0
                elif target_kpi in ["열차이용 쾌적성"]:
                    st.session_state.future_selected_modes = [] # Clear PAI-specific modes
                    future_kpi_val = (future_val1 / future_val2) * 100 if future_val2 > 0 else 0
                    future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                    calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
                elif target_kpi in ["역사 시설 쾌적성", "환승시설 쾌적성"]:
                    st.session_state.future_selected_modes = [] # Clear PAI-specific modes
                    future_kpi_val = (future_val1 / future_val2) if future_val2 > 0 else 0
                    future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                    calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
                else: # Default case for other KPIs
                    st.session_state.future_selected_modes = [] # Clear PAI-specific modes
                    future_kpi_val = future_val1
                    future_kpi_val_safe = future_kpi_val if future_kpi_val is not None else 0.0
                    calculated_predict_score = m2.calculate_satisfaction(rail_type, abbreviated_kpi, future_kpi_val_safe)
            if not st.session_state.predict_score_is_manual:
                st.session_state.predict_score = calculated_predict_score


            st.write(f"다. {kpi_display_name}의 **장래연도 목표**를 입력해주세요.")
            
            goal_col1, goal_col2, goal_col3 = st.columns([1, 2, 2])
            with goal_col1:
                st.radio("목표 입력 방식", ['성과지표', '만족도'], key='goal_input_method', label_visibility='collapsed')

            is_score_input = st.session_state.goal_input_method == '만족도'
            
            with goal_col2:
                st.number_input(f"목표 성과지표 값 ({unit})", key='future_goal_kpi_input', on_change=update_goal_score_from_kpi, disabled=is_score_input, step=1.0, format="%.2f")
            with goal_col3:
                st.number_input("목표 만족도 점수", key='future_goal_score_input', on_change=update_goal_kpi_from_score, disabled=not is_score_input, min_value=0.0, max_value=10.0, step=0.1, format="%.1f")

            st.write(f"라. {kpi_display_name}의 **장래연도 예상 만족도**를 입력해주세요.")
            st.number_input("예상 만족도 점수", placeholder=predict_score_placeholder, key='predict_score', on_change=handle_manual_predict_score_change, min_value=0.0, max_value=10.0, step=0.1, disabled=not inputs_are_valid)
            
            part2_inputs_are_valid = all(st.session_state.get(k) is not None for k in ['future_goal_score_input', 'predict_score', 'target_year_input', 'target_month_input'])
            
            if inputs_are_valid and part2_inputs_are_valid:
                target_year = int(st.session_state.target_year_input)
                target_month = int(st.session_state.target_month_input)
                future_predict_score = st.session_state.predict_score
                future_goal_score = st.session_state.future_goal_score_input
                abbreviated_kpi = KPI_ABBREVIATIONS.get(target_kpi, target_kpi)

                if target_kpi == "환승시설 편의성":
                    future_predict_val = future_predict_score
                    if st.session_state.goal_input_method == '성과지표':
                        future_goal_val = st.session_state.future_goal_kpi_input
                    else:
                        future_goal_val = future_goal_score
                else:
                    future_predict_val = m2.reverse_calculate_value(rail_type, abbreviated_kpi, future_predict_score)
                    if st.session_state.goal_input_method == '성과지표':
                        future_goal_val = st.session_state.future_goal_kpi_input
                    else:
                        future_goal_val = m2.reverse_calculate_value(rail_type, abbreviated_kpi, future_goal_score)

                is_fail = future_predict_score < future_goal_score
            
    _, reset_col = st.columns([5, 1])
    with reset_col:
        st.button("🔄 모든 입력 초기화", on_click=reset_user_inputs, use_container_width=True)

#==============================================================
#3. 성과지표 변화 추이 및 만족도 결과 요약
#==============================================================
    with st.container(border=True):
        st.markdown(f'<div class="header-box green-box">3. {target_kpi} 변화 추이 및 만족도 결과 요약</div>', unsafe_allow_html=True)
        
        if inputs_are_valid and part2_inputs_are_valid and is_fail:
            st.error(f"🚨 분석 결과, 예측 만족도({future_predict_score:.2f}점)가 목표 만족도({future_goal_score:.2f}점)에 미달할 것입니다.")
        elif inputs_are_valid and part2_inputs_are_valid:
            st.success(f"✅ 예측 만족도({future_predict_score:.2f}점)가 목표 만족도({future_goal_score:.2f}점)를 초과 달성했습니다.")

        bottom_chart_col, bottom_summary_col = st.columns(2)

        with bottom_chart_col:
            st.write("가. 지표 변화 추이")
            y_scale_domain = alt.Undefined
            if inputs_are_valid and part2_inputs_are_valid:
                y_vals = [v for v in [current_val, future_predict_val, future_goal_val] if v is not None and np.isfinite(v)]
                
                if y_vals:
                    buffer_ratio = 0.10
                    data_min = min(y_vals)
                    data_max = max(y_vals)

                    if data_min == data_max:
                        buffer = abs(data_min * buffer_ratio) or 1
                        y_min_limit = data_min - buffer
                        y_max_limit = data_max + buffer
                    else:
                        min_buffer = abs(data_min * buffer_ratio)
                        max_buffer = abs(data_max * buffer_ratio)
                        y_min_limit = data_min - min_buffer
                        y_max_limit = data_max + max_buffer
                    
                    if y_min_limit >= y_max_limit:
                        y_min_limit = y_max_limit - 1

                    y_scale_domain = [round(y_min_limit), round(y_max_limit)]

            chart_data = pd.DataFrame({ '시점': ['현재', f'{target_year}년'], '예측치': [current_val, future_predict_val], '목표치': [current_val, future_goal_val] })
            alt_chart_data = chart_data.melt('시점', var_name='구분', value_name='값')
            
            base_chart = alt.Chart(alt_chart_data).mark_line(point=True).encode(
                x=alt.X('시점', sort=['현재', f'{target_year}년'], title='시점'),
                y=alt.Y('값', title=f'{target_kpi} ({unit})', scale=alt.Scale(domain=y_scale_domain)),
                color='구분',
                tooltip=['시점', '구분', '값']
            ).configure_title(
                fontSize=15,
                anchor='middle'
            ).configure_axis(
                labelFontSize=11,
                titleFontSize=13
            )

            line_chart = base_chart.properties(title=f"{target_kpi} 변화 예측", height=300)
            line_chart_pdf = base_chart.properties(title=f"{target_kpi} 변화 예측", width=500, height=250)
            
            st.altair_chart(line_chart, use_container_width=True)
            
        with bottom_summary_col:
            st.write("나. 결과 요약")
            comp_df = pd.DataFrame({ "구분": ["현재", f"{target_year}년 예측", f"{target_year}년 목표"], f"{target_kpi}": [f"{current_val:.2f}{unit}", f"{future_predict_val:.2f}{unit}", f"{future_goal_val:.2f}{unit}"], "만족도": [f"{current_score:.2f}점", f"{future_predict_score:.2f}점", f"{future_goal_score:.2f}점"] }).set_index("구분").T
            st.dataframe(comp_df, use_container_width=True)

#==============================================================
#4. 추진과제 분석 결과 및 정책 수행 제언
#==============================================================
    st.divider()
    with st.container(border=True):
        st.markdown('<div class="header-box purple-box">4. 추진과제 분석 결과 및 정책 수행 제언</div>', unsafe_allow_html=True)
        table_data = pd.DataFrame()
        active_policies = pd.DataFrame()
        if inputs_are_valid and part2_inputs_are_valid and is_fail:
            target_date = datetime(target_year, target_month, 1) + relativedelta(months=1) - relativedelta(days=1)
            policy_df = st.session_state['policy_db']
            if 'related_kpi' in policy_df.columns:
                table_data = policy_df[policy_df['related_kpi'].str.contains(target_kpi, na=False)].copy()
            else:
                table_data = policy_df.copy()
            
            st.write(f"가. '{target_kpi}' 개선을 위해 다음 정책들을 수행해야 합니다.")
            
            if not table_data.empty:
                if 'loaded_active_names' in st.session_state and st.session_state.loaded_active_names:
                    table_data['active'] = table_data['name'].isin(st.session_state.loaded_active_names)
                    del st.session_state.loaded_active_names
                elif 'active' not in table_data.columns:
                    table_data['active'] = False
                start_dates = [(target_date - relativedelta(months=int(row['duration_months']))).strftime('%Y년 %m월') for _, row in table_data.iterrows()]
                table_data['start_date_calc'] = start_dates
                table_data['duration_months_display'] = table_data['duration_months'].astype(str) + " 개월"

        st.session_state.edited_policies_df = st.data_editor(table_data, column_config={"active": st.column_config.CheckboxColumn("활성화", default=False), "category": "분야", "name": "추진 과제명", "cost": "추진 사업비", "process": "추진 절차", "duration_months_display": st.column_config.TextColumn("추진 기간", disabled=True), "start_date_calc": st.column_config.TextColumn("추진 시작 시기", disabled=True)}, hide_index=True, use_container_width=True, column_order=['active', 'category', 'name', 'cost', 'process', 'duration_months_display', 'start_date_calc'])
        
        if 'active' in st.session_state.edited_policies_df.columns:
            active_policies = st.session_state.edited_policies_df[st.session_state.edited_policies_df['active']]

        st.write(f"나. 과제별 소요기간 그래프")
        
        timeline_df = pd.DataFrame()
        if not active_policies.empty:
            source_for_chart = st.session_state.policy_db.loc[active_policies.index]
            timeline_df = m4.create_timeline_data(source_for_chart, target_year, target_month)
        
        project_end_date = timeline_df['End'].max() if not timeline_df.empty else datetime(target_year, target_month, 1)
        max_duration = 0
        if not table_data.empty:
            durations = pd.to_numeric(table_data['duration_months'], errors='coerce').dropna()
            if not durations.empty:
                max_duration = int(durations.max())
        max_date = project_end_date + relativedelta(weeks=1)
        min_date = project_end_date - relativedelta(months=(max_duration or 12) + 1)
        
        gray_area_df = pd.DataFrame([{'start': project_end_date, 'end': max_date}])
        gray_area = alt.Chart(gray_area_df).mark_rect(color='lightgray', opacity=0.3).encode(x='start', x2='end')
        now_line = alt.Chart(pd.DataFrame({'now': [datetime.now()]})).mark_rule(color='red', strokeDash=[5, 5]).encode(x='now')
        target_line = alt.Chart(pd.DataFrame({'date': [project_end_date]})).mark_rule(color='darkblue', strokeWidth=1.5, strokeDash=[3,3]).encode(x='date')
        final_chart = gray_area + target_line
        
        if not timeline_df.empty:
            chart = alt.Chart(timeline_df).mark_bar().encode(
                x=alt.X('Start', title='추진 기간', scale=alt.Scale(domain=[min_date, max_date]), axis=alt.Axis(grid=True, gridColor='lightgray', gridDash=[1,1], tickCount={'interval': 'month', 'step': 3}, labelExpr='month(datum.value) == 0 ? timeFormat(datum.value, "%Y년") : ""', labelAngle=0, labelSeparation=5, tickSize=10)),
                x2=alt.X2('End'),
                y=alt.Y('Project', title='추진 과제', sort=None, axis=alt.Axis(labelLimit=0)),
                color=alt.Color('Category', title='분야', scale=alt.Scale(domain=['철도 건설', '철도 시설', '철도 운영', '연계교통'], range=['#F5BC9E', '#8092A8', '#AECCE4', '#A8C8A8'])) ,
                tooltip=['Project', 'Start', 'End', 'Duration']
            )
            final_chart += chart
        
        if datetime.now() >= min_date:
            final_chart += now_line
        
        if not timeline_df.empty:
            final_chart = final_chart.properties(width=650, height=alt.Step(40))
        else:
            final_chart = final_chart.properties(width=650, height=100)

        st.altair_chart(final_chart, use_container_width=True)
        st.caption("🔴 빨간 점선: 현재 시점 ┃ 🔵 파란 점선: 목표 시점")
        
        if inputs_are_valid and part2_inputs_are_valid and is_fail:
            st.divider()
            st.write("다. 종합 분석 및 제언")

            station_info_kpis = ["물리적 접근성", "시간적 접근성", "환승시설 편의성", "역사 시설 쾌적성", "환승시설 쾌적성"]
            if target_kpi in station_info_kpis:
                line1 = f"{st.session_state.station_name_input}({st.session_state.line_name})에 대해 현재와 장래의 {target_kpi}와 그에 따른 만족도 분석을 수행하였습니다."
            else:
                line1 = f"{st.session_state.line_name}({st.session_state.start_station_input}~{st.session_state.end_station_input}, {st.session_state.line_length_input}km) 구간에 대해 현재와 장래의 {target_kpi}와 그에 따른 만족도 분석을 수행하였습니다."
            
            line2 = f"· 현재 해당 구간 {target_kpi} : {current_val:.1f}{unit}, {current_score:.1f}점(10점 만점)"
            line3 = f"· 장래 해당 구간 예상 {target_kpi} : {future_predict_val:.2f}{unit}, {future_predict_score:.2f}점(10점 만점)"
            line4 = f"· 장래 해당 구간 목표 {target_kpi} : {future_goal_val:.2f}{unit}, {future_goal_score:.2f}점(10점 만점)"
            st.markdown(line1)
            st.markdown(line2)
            st.markdown(line3)
            st.markdown(line4)

            diff = future_goal_val - future_predict_val
            comparison_text = "높아" if future_predict_val > future_goal_val else "낮아"

            if future_goal_val > 0 and unit != '%':
                percentage_diff_text = f" ({(abs(diff) / future_goal_val) * 100:.0f}%)"
            else:
                percentage_diff_text = ""
            
            diff_display = f"{abs(diff):.2f}{unit}{percentage_diff_text}"

            text1 = f"그 결과, **{target_kpi}** 목표치({future_goal_val:.2f}{unit})에 비해 장래 예측치({future_predict_val:.2f}{unit})가 **{diff_display} {comparison_text},** 정책 달성을 위한 철도 추진과제 시행이 필요합니다."
            st.markdown(text1)

            now = datetime.now()
            available_projects_list = []
            long_term_projects_list = []

            if 'duration_months' in table_data.columns and not table_data.empty:
                target_date = datetime(target_year, target_month, 1) + relativedelta(months=1) - relativedelta(days=1)
                for _, row in table_data.iterrows():
                    try:
                        duration = int(row['duration_months'])
                    except (ValueError, TypeError):
                        continue
    
                    required_start_date = target_date - relativedelta(months=duration)
                    if required_start_date >= now:
                        start_str = required_start_date.strftime('%Y년 %m월')
                        available_projects_list.append(f" - {row['name']}({start_str}부터 추진, {duration}개월 소요)")
                    else:
                        finish_date_if_started_now = now + relativedelta(months=duration)
                        months_late = (finish_date_if_started_now.year - target_date.year) * 12 + finish_date_if_started_now.month - target_date.month
                        if months_late > 0:
                            long_term_projects_list.append(f" - {row['name']}({duration}개월 소요, {finish_date_if_started_now.strftime('%Y년 %m월')} 완료 예상)")
                        
            if available_projects_list:
                st.markdown("현재 추진 가능한 철도 추진과제는 다음과 같습니다.")
                st.markdown("\n".join(available_projects_list[:3]))
            
            st.write("") 

            if long_term_projects_list:
                st.markdown(f"다음과 같은 정책의 추진을 고려할 수 있으나, 정책 추진에 장기간 소요되어 **목표연도({target_year}년 {target_month}월)** 내에 구축이 불가능해 정책 달성이 어렵습니다.")
                st.markdown("\n".join(long_term_projects_list[:3]))

            st.write("") 
            st.markdown("비용과 일정을 참고하여 추진가능한 철도과제를 상단 표에서 다시 한번 확인하시어, 철도 정책 달성에 참고하시기 바랍니다.")
        
    st.divider()
    _, right_container = st.columns([1, 1])
    with right_container:
        st.write("시나리오 저장 및 불러오기")
        save_col, manage_col = st.columns(2)
        with save_col:
            st.write("시나리오 저장")
            if st.session_state.get('loaded_scenario_name'):
                button_label = f"'{st.session_state.loaded_scenario_name}'에 덮어쓰기"
                file_name = st.session_state.loaded_scenario_name
            else:
                line_name_safe = sanitize_filename(st.session_state.get('line_name', '선택안함'))
                section_safe = sanitize_filename(st.session_state.get('line_section_input', '선택안함'))
                kpi_safe = sanitize_filename(st.session_state.get('target_kpi', '선택안함'))
                auto_filename = f"{line_name_safe}-{section_safe}-{kpi_safe}.csv"
                button_label = "현재 시나리오 다운로드"
                file_name = auto_filename
            csv_data = get_scenario_as_csv_string()
            st.download_button(
               label=button_label,
               data=csv_data,
               file_name=file_name,
               mime='text/csv',
               use_container_width=True
            )
    
            st.write("") 
    
            if inputs_are_valid and part2_inputs_are_valid:
                try:
                    analysis_proposal_texts = []
                    if is_fail:
                        station_info_kpis = ["물리적 접근성", "시간적 접근성", "환승시설 편의성", "역사 시설 쾌적성", "환승시설 쾌적성"]
                        if target_kpi in station_info_kpis:
                            line1 = f"{st.session_state.station_name_input}({st.session_state.line_name})에 대해 현재와 장래의 {target_kpi}와 그에 따른 만족도 분석을 수행하였습니다."
                        else:
                            line1 = f"{st.session_state.line_name}({st.session_state.start_station_input}~{st.session_state.end_station_input}, {st.session_state.line_length_input}km) 구간에 대해 현재와 장래의 {target_kpi}와 그에 따른 만족도 분석을 수행하였습니다."
                        
                        line2 = f"· 현재 해당 구간 {target_kpi} : {current_val:.1f}{unit}, {current_score:.1f}점(10점 만점)"
                        line3 = f"· 장래 해당 구간 예상 {target_kpi} : {future_predict_val:.2f}{unit}, {future_predict_score:.2f}점(10점 만점)"
                        line4 = f"· 장래 해당 구간 목표 {target_kpi} : {future_goal_val:.2f}{unit}, {future_goal_score:.2f}점(10점 만점)"
                        analysis_proposal_texts.append(line1)
                        analysis_proposal_texts.append(line2)
                        analysis_proposal_texts.append(line3)
                        analysis_proposal_texts.append(line4)

                        diff = future_goal_val - future_predict_val
                        comparison_text = "높아" if future_predict_val > future_goal_val else "낮아"

                        if future_goal_val > 0 and unit != '%':
                            percentage_diff_text = f" ({(abs(diff) / future_goal_val) * 100:.0f}%)"
                        else:
                            percentage_diff_text = ""
                        
                        diff_display = f"{abs(diff):.2f}{unit}{percentage_diff_text}"

                        text1 = f"그 결과, **{target_kpi}** 목표치({future_goal_val:.2f}{unit})에 비해 장래 예측치({future_predict_val:.2f}{unit})가 **{diff_display} {comparison_text},** 정책 달성을 위한 철도 추진과제 시행이 필요합니다."
                        analysis_proposal_texts.append(text1)
                        
                        now = datetime.now()
                        available_projects_list = []
                        long_term_projects_list = []
                        
                        if 'duration_months' in table_data.columns and not table_data.empty:
                            target_date = datetime(target_year, target_month, 1) + relativedelta(months=1) - relativedelta(days=1)
                            for _, row in table_data.iterrows():
                                try:
                                    duration = int(row['duration_months'])
                                except (ValueError, TypeError):
                                    continue
    
                                required_start_date = target_date - relativedelta(months=duration)
                                if required_start_date >= now:
                                    start_str = required_start_date.strftime('%Y년 %m월')
                                    available_projects_list.append(f" - {row['name']}({start_str}부터 추진, {duration}개월 소요)")
                                else:
                                    finish_date_if_started_now = now + relativedelta(months=duration)
                                    months_late = (finish_date_if_started_now.year - target_date.year) * 12 + finish_date_if_started_now.month - target_date.month
                                    if months_late > 0:
                                        long_term_projects_list.append(f" - {row['name']}({duration}개월 소요, {finish_date_if_started_now.strftime('%Y년 %m월')} 완료 예상)")
                        
                        if available_projects_list:
                            analysis_proposal_texts.append("현재 추진 가능한 철도 추진과제는 다음과 같습니다.")
                            analysis_proposal_texts.extend(available_projects_list[:3])
                        
                        if long_term_projects_list:
                            analysis_proposal_texts.append(f"다음과 같은 정책의 추진을 고려할 수 있으나, 정책 추진에 장기간 소요되어 **목표연도 ({target_year}년 {target_month}월)** 내에 구축이 불가능해 정책 달성이 어렵습니다.")
                            analysis_proposal_texts.extend(long_term_projects_list[:3])
                        
                        final_text = "비용과 일정을 참고하여 추진가능한 철도과제를 상단 표에서 다시 한번 확인하시어, 철도 정책 달성에 참고하시기 바랍니다."
                        analysis_proposal_texts.append(final_text)
    
                    report_data = {
                        'target_kpi': target_kpi, 'rail_type': rail_type, 'line_name': st.session_state.line_name,
                        'station_name_input': st.session_state.get('station_name_input'),
                        'start_station_input': st.session_state.start_station_input, 'end_station_input': st.session_state.end_station_input,
                        'line_section_input': st.session_state.line_section_input, 'line_length_input': st.session_state.line_length_input,
                        'input_val_1': st.session_state.input_val_1, 'input_val_2': st.session_state.input_val_2, 'input_minute': st.session_state.input_minute,
                        'current_val': current_val, 'current_score': current_score, 'unit': unit, 'sens_df': sens_df, 'target_year': target_year,
                        'target_month': target_month, 'future_input_val_1': st.session_state.future_input_val_1,
                        'future_input_val_2': st.session_state.future_input_val_2, 'future_input_minute': st.session_state.future_input_minute,
                        'predict_score': st.session_state.predict_score, 'goal_input_method': st.session_state.goal_input_method,
                        'future_goal_kpi_input': st.session_state.future_goal_kpi_input, 'future_goal_score_input': st.session_state.future_goal_score_input,
                        'summary_df': comp_df, 'line_chart': line_chart_pdf, 'is_fail': is_fail,
                        'future_predict_score': future_predict_score, 'future_goal_score': future_goal_score,
                        'future_predict_val': future_predict_val, 'future_goal_val': future_goal_val,
                        'active_policies': st.session_state.edited_policies_df, 'timeline_chart': final_chart,
                        'analysis_proposal': analysis_proposal_texts,
                        'current_selected_modes': st.session_state.get('current_selected_modes', []),
                        'future_selected_modes': st.session_state.get('future_selected_modes', []),
                    }
                    
                    with st.spinner('PDF 보고서를 생성하는 중입니다...'):
                        pdf_bytes = m5.generate_report(report_data)
                    
                    kpi_safe = sanitize_filename(st.session_state.get('target_kpi', '선택안함'))
                    pdf_file_name = f"성과분석_보고서_{sanitize_filename(st.session_state.line_name)}_{kpi_safe}.pdf"
                    
                    st.download_button(
                        label="📄 PDF 보고서 다운로드",
                        data=pdf_bytes,
                        file_name=pdf_file_name,
                        mime='application/pdf',
                        use_container_width=True,
                        key='pdf_download_button'
                    )
                except Exception as e:
                    st.error(f"PDF 생성 중 오류 발생: {e}")

        with manage_col:
            st.write("시나리오 불러오기")
            st.file_uploader("업로드 즉시 적용됩니다", type=['csv'], accept_multiple_files=True, key="scenario_multi_uploader", on_change=process_uploaded_scenario, label_visibility="collapsed")