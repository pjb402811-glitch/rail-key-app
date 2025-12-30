# -*- coding: utf-8 -*-
# M3-4: Admin View

import streamlit as st
from m1 import DataManager, resource_path
from m6 import SurveyAnalyzer
import pandas as pd
from m3_1 import SELECT_PLACEHOLDER

def draw_admin_view():
    """관리자 페이지를 그립니다."""
    
    title_col, button_col = st.columns([0.8, 0.2])
    with title_col:
        st.title("🔒 관리자 페이지")
    with button_col:
        if st.button("🏠 초기 화면으로 돌아가기", use_container_width=True):
            st.session_state.view_mode = 'landing'
            st.session_state.logged_in = False # 항상 로그아웃 처리
            st.rerun()

    if not st.session_state.get('logged_in', False):
        draw_login_form()
    else:
        draw_admin_dashboard()

def draw_login_form():
    """로그인 폼을 그립니다."""
    with st.form("login_form"):
        username = st.text_input("사용자 이름")
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("로그인")

        if submitted:
            if username == "admin" and password == "admin":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("사용자 이름 또는 비밀번호가 잘못되었습니다.")

def draw_admin_dashboard():
    """데이터 편집 및 관리용 대시보드를 그립니다."""
    m1_instance = DataManager()

    # --- 복원 확인 다이얼로그 ---
    @st.dialog("초기 복원 확인")
    def confirm_restore_dialog(restore_function, target_name):
        st.warning(f"{target_name} 데이터를 초기 상태로 복원하시겠습니까? 이 작업은 되돌릴 수 없습니다.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("예, 복원합니다", use_container_width=True, type="primary"):
                restore_function()
                if 'policy_df_editor' in st.session_state and ('추진 과제' in target_name or '전체' in target_name):
                    del st.session_state.policy_df_editor
                if 'coeffs_df_editor' in st.session_state and ('만족도 계수' in target_name or '전체' in target_name):
                    del st.session_state.coeffs_df_editor
                st.rerun()
        with col2:
            if st.button("아니오, 취소합니다", use_container_width=True):
                st.rerun()

    # --- 다운로드 다이얼로그 ---
    @st.dialog("설문조사지 다운로드")
    def show_survey_QnA_popup():
        st.write("최초 용역인 서울과학기술대학교의 용역(2025)에서는 성과지표를 3개로 나눠, 총 3개의 철도 분류(고속, 일반, 광역)에 대해 총 9가지 설문지를 작성하여 설문조사 용역을 수행하였습니다.")
        st.write("\n설문조사 용역에 참고하시기 바랍니다.\n")
        st.write("아래 버튼을 클릭해, 설문조사지 파일을 다운로드하세요.")
        with open(resource_path("data/docs/설문조사지.zip"), "rb") as fp:
            st.download_button("설문조사지.zip 다운로드", fp, "설문조사지.zip", "application/zip", use_container_width=True)

    @st.dialog("설문조사 결과양식 다운로드")
    def show_survey_result_popup():
        st.write("모형 분석을 위한 설문조사 결과양식을 다운로드하세요.\n")
        st.write("결과 양식은 다음과 같이 구성됩니다.")
        st.write("· [선택] respond_ID : 응답자 ID")
        st.write("· [필수] KPI : 성과지표, 응답자가 만족도 점수 분류를 위해, 설문조사지에서 제시한 성과지표")
        st.write("· [필수] Satisfaction : 만족도, 응답자가 응답한 만족도로 **10점 만점** 기준")
        st.write("\n엑셀에서 저장할 때는 CSV UTF-8(쉼표로 분리)(*.csv) 양식으로 저장해주세요.")
        with open(resource_path("data/docs/설문결과 분석 양식.csv"), "rb") as fp:
            st.download_button("양식 파일 다운로드", fp, "설문결과 분석 양식.csv", "text/csv", use_container_width=True)

    st.info("이곳에서 시스템의 주요 데이터를 관리할 수 있습니다. 데이터를 수정한 후에는 반드시 '저장' 버튼을 눌러주세요.")

    tab2, tab3, tab4 = st.tabs(["추진 과제 관리", "설문조사 결과 입력 및 만족도 계수 산출", "만족도 계수 관리"])

    with tab2:
        st.header("추진 과제 관리 (policy_db.csv)")
        if 'policy_df_editor' not in st.session_state:
            st.session_state.policy_df_editor = m1_instance.load_policy_data()
        
        policy_column_config = {
            "category": st.column_config.TextColumn("분야"),
            "name": st.column_config.TextColumn("추진 과제명"),
            "cost": st.column_config.TextColumn("추진 사업비"),
            "process": st.column_config.TextColumn("추진 절차"),
            "duration_months": st.column_config.NumberColumn("추진 기간 (개월)"),
            "related_kpi": st.column_config.TextColumn("관련 성과지표")
        }
        edited_policy_df = st.data_editor(
            st.session_state.policy_df_editor, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config=policy_column_config
        )
        
        if st.button("💾 추진 과제 변경사항 저장", key="save_policy", use_container_width=True): 
            m1_instance.save_policy_data(edited_policy_df)
            st.session_state.policy_df_editor = edited_policy_df
            st.toast("✅ 추진 과제 데이터가 성공적으로 저장되었습니다.")
        
        st.divider()
        _, restore_policy_col, restore_all_col_1 = st.columns([0.7, 0.15, 0.15])
        with restore_policy_col:
            if st.button("추진 과제 초기 복원", key="restore_policy", use_container_width=True):
                confirm_restore_dialog(m1_instance.restore_policy_data, "추진 과제")
        with restore_all_col_1:
            if st.button("전체 초기 복원", key="restore_all_tab2", use_container_width=True, type="primary", help="추진과제, 만족도 계수 등 수정된 모든 데이터를 초기화합니다."):
                confirm_restore_dialog(m1_instance.restore_all_data, "전체")

    with tab3:
        st.header("설문조사 결과 입력 및 만족도 계수 산출")
        st.write("설문조사 데이터를 업로드하여 만족도 계수를 자동으로 산출하고 시스템에 반영합니다.")

        _, qna_button_col, result_button_col = st.columns([0.7, 0.15, 0.15])
        with qna_button_col:
            if st.button("ℹ️ 설문조사지 다운로드", use_container_width=True):
                show_survey_QnA_popup()
        with result_button_col:
            if st.button("ℹ️ 분석 양식 다운로드", use_container_width=True):
                show_survey_result_popup()

        analyzer = SurveyAnalyzer()

        rail_type_col, kpi_col, model_col = st.columns(3)
        with rail_type_col:
            selected_rail_type = st.selectbox("철도 유형 선택", [SELECT_PLACEHOLDER] + list(m1_instance.load_coefficients()[0]['coefficients'].keys()), key="selected_survey_rail_type")
        with kpi_col:
            selected_kpi_name_kor = st.selectbox(
                "성과지표 선택",
                options=[SELECT_PLACEHOLDER] + list(m1_instance.KPI_ABBREVIATIONS.keys()),
                format_func=lambda k: f"{k} ({m1_instance.KPI_ABBREVIATIONS.get(k, '')})" if k != SELECT_PLACEHOLDER else SELECT_PLACEHOLDER,
                key="selected_survey_kpi_name_kor"
            )
        with model_col:
            model_options = {
                'A': 'A: 한계효용체감',
                'B': 'B: S자형 로지스틱',
                'C': 'C: 역 지수 함수'
            }
            st.selectbox(
                "만족도 모델 선택",
                options=list(model_options.keys()),
                format_func=lambda x: model_options[x],
                key="selected_model_type"
            )

        uploaded_file = st.file_uploader("설문조사 데이터 파일 업로드 (CSV)", type=["csv"], key="survey_upload")

        if uploaded_file:
            try:
                survey_df = pd.read_csv(uploaded_file, encoding='utf-8')
                st.subheader("업로드된 설문조사 데이터 미리보기")
                st.dataframe(survey_df)

                required_cols = ['KPI', 'Satisfaction']
                if not all(col in survey_df.columns for col in required_cols):
                    st.error(f"업로드된 파일에 필수 컬럼이 누락되었습니다. 필요 컬럼: {', '.join(required_cols)}")
                    st.stop()

                calc_df = survey_df.rename(columns={'KPI': 'kpi_value', 'Satisfaction': 'satisfaction_score'})

                if st.button("계수 산출 및 미리보기", key="calculate_coeffs_btn"):
                    if selected_rail_type == SELECT_PLACEHOLDER or selected_kpi_name_kor == SELECT_PLACEHOLDER:
                        st.error("철도 유형과 성과지표를 모두 선택해야 합니다.")
                    else:
                        with st.spinner("계수 산출 중..."):
                            calculated_coeffs_df, stats = analyzer.calculate_coefficients(
                                selected_rail_type, selected_kpi_name_kor, calc_df, 
                                model_type=st.session_state.selected_model_type,
                                original_filename=uploaded_file.name
                            )
                            if not calculated_coeffs_df.empty:
                                st.session_state.calculated_coeffs_df = calculated_coeffs_df
                                st.session_state.calculated_stats = stats
                                st.rerun()
                            else:
                                st.warning("계수를 산출하지 못했습니다. 데이터와 선택값을 확인해주세요.")
            except Exception as e:
                st.error(f"파일 처리 중 오류 발생: {e}")
        
        if 'calculated_coeffs_df' in st.session_state and not st.session_state.calculated_coeffs_df.empty:
            st.subheader("산출된 계수 미리보기")
            st.dataframe(st.session_state.calculated_coeffs_df)

            if 'calculated_stats' in st.session_state and st.session_state.calculated_stats:
                st.subheader("통계적 유의수준")
                stats = st.session_state.calculated_stats
                col1, col2, col3 = st.columns(3)
                col1.metric("SSE", f"{stats['SSE']:.4f}")
                col2.metric("SST", f"{stats['SST']:.4f}")
                col3.metric("R-squared", f"{stats['R-squared']:.4f}")
            
            st.warning("경고: 기존 만족도 계수는 새로 산출된 계수로 덮어쓰여집니다.")
            
            if st.button("산출된 계수 저장", key="save_calculated_coeffs_btn", use_container_width=True):
                try:
                    existing_coeffs_df = m1_instance.load_coefficients_df()
                    new_coeffs_to_update = st.session_state.calculated_coeffs_df
                    
                    # rail_type과 kpi를 모두 고려하여 기존 계수를 올바르게 제거
                    # 예: '고속철도'의 'TC' 계수를 업데이트할 때 '일반철도'의 'TC' 계수는 유지됩니다.
                    rows_to_drop = (existing_coeffs_df['rail_type'].isin(new_coeffs_to_update['rail_type'])) & \
                                   (existing_coeffs_df['kpi'].isin(new_coeffs_to_update['kpi']))
                    
                    updated_coeffs_df = existing_coeffs_df[~rows_to_drop].copy()
                    
                    # drop(columns=['model_type'], errors='ignore') 추가: 해당 컬럼이 없을 때 오류 방지
                    updated_coeffs_df = pd.concat([updated_coeffs_df, new_coeffs_to_update.drop(columns=['model_type'], errors='ignore')], ignore_index=True)
                    
                    m1_instance.save_coefficients(updated_coeffs_df)
                    st.success("새롭게 산출된 계수가 성공적으로 저장되었습니다.")
                    del st.session_state.calculated_coeffs_df
                    if 'calculated_stats' in st.session_state:
                        del st.session_state.calculated_stats
                    st.rerun()
                except Exception as e:
                    st.error(f"계수 저장 중 오류 발생: {e}")

    with tab4:
        st.header("만족도 계수 관리 (coefficients.csv)")

        _, refresh_col = st.columns([0.85, 0.15])
        with refresh_col:
            if st.button("🔄 데이터 새로고침", key="refresh_coeffs", use_container_width=True):
                if 'coeffs_df_editor' in st.session_state:
                    del st.session_state.coeffs_df_editor
                    st.toast("✅ 계수 데이터를 파일에서 새로고침했습니다.")
                else:
                    st.toast("ℹ️ 아직 불러온 데이터가 없습니다.")
                st.rerun()


        if 'coeffs_df_editor' not in st.session_state:
            df = m1_instance.load_coefficients_df()
            df['성과지표'] = df['kpi'].map(m1_instance.ABBREVIATIONS_TO_FULL_NAMES)
            st.session_state.coeffs_df_editor = df
        
        coeffs_column_config = {
            "rail_type": st.column_config.TextColumn("철도 유형"),
            "kpi": None,
            "성과지표": st.column_config.SelectboxColumn("성과지표", options=list(m1_instance.KPI_ABBREVIATIONS.keys()), required=True),
            "param1_name": st.column_config.TextColumn("계수 1 이름"),
            "param1_value": st.column_config.NumberColumn("계수 1 값"),
            "param2_name": st.column_config.TextColumn("계수 2 이름"),
            "param2_value": st.column_config.NumberColumn("계수 2 값"),
        }

        edited_coeffs_df = st.data_editor(
            st.session_state.coeffs_df_editor, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config=coeffs_column_config,
            column_order=["rail_type", "성과지표", "param1_name", "param1_value", "param2_name", "param2_value"]
        )

        if st.button("💾 만족도 계수 변경사항 저장", key="save_coeffs", use_container_width=True):
            df_to_save = edited_coeffs_df.copy()
            df_to_save['kpi'] = df_to_save['성과지표'].map(m1_instance.KPI_ABBREVIATIONS)
            df_to_save = df_to_save.drop(columns=['성과지표'])
            df_to_save = df_to_save[['rail_type', 'kpi', 'param1_name', 'param1_value', 'param2_name', 'param2_value']]
            m1_instance.save_coefficients(df_to_save)
            st.session_state.coeffs_df_editor = edited_coeffs_df
            st.toast("✅ 만족도 계수 데이터가 성공적으로 저장되었습니다.")
        
        st.divider()
        _, restore_coeffs_col, restore_all_col_2 = st.columns([0.7, 0.15, 0.15])
        with restore_coeffs_col:
            if st.button("만족도 계수 초기 복원", key="restore_coeffs", use_container_width=True):
                confirm_restore_dialog(m1_instance.restore_coefficients_data, "만족도 계수")
        with restore_all_col_2:
            if st.button("전체 초기 복원", key="restore_all_tab4", use_container_width=True, type="primary", help="추진과제, 만족도 계수 등 수정된 모든 데이터를 초기화합니다."):
                confirm_restore_dialog(m1_instance.restore_all_data, "전체")
