# -*- coding: utf-8 -*-
# M1: 데이터 매니저 (정책 DB 로드)
import pandas as pd
import shutil
import os
import sys  # .exe 파일 경로 관련 모듈
import streamlit as st # Streamlit import for UI feedback

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def user_data_path(relative_path):
    """ Get path to a user-writable file, works for dev and for PyInstaller """
    try:
        # Running as a bundled exe - use user's home directory
        # getattr is used to check if 'frozen' attribute exists, which indicates a bundled app
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = os.path.join(os.path.expanduser('~'), 'RailIndicatorApp')
        else:
            # Running as a script - use current working directory
            base_path = os.path.abspath(".")
    except Exception:
        base_path = os.path.abspath(".")

    # Ensure the target directory exists
    target_dir = os.path.join(base_path, os.path.dirname(relative_path))
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    return os.path.join(base_path, relative_path)

class DataManager:

    KPI_ABBREVIATIONS = {
        "물리적 접근성": "PAI",
        "시간적 접근성": "TAI",
        "경제적 접근성": "EAI",
        "운행횟수": "TF",
        "표정속도": "TV",
        "열차운행 정시성": "TOTP",
        "환승시설 편의성": "TCI",
        "역사 시설 쾌적성": "SC",
        "열차이용 쾌적성": "TC",
        "환승시설 쾌적성": "TPC"
    }
    
    TCI_ALL_MODES = ['대중교통', '도보', '승용차', '택시/배웅', 'PM']
    
    ABBREVIATIONS_TO_FULL_NAMES = {v: k for k, v in KPI_ABBREVIATIONS.items()}

    def __init__(self):
        # 읽기 전용 원본 데이터 경로 (.exe 내부 또는 소스 data 폴더)
        self.original_policy_path = resource_path(os.path.join('data', 'policy_db.csv'))
        self.original_coeffs_path = resource_path(os.path.join('data', 'coefficients.csv'))

        # 수정/저장이 가능한 데이터 경로 (사용자 폴더 또는 소스 data 폴더)
        self.modified_policy_path = user_data_path(os.path.join('data', 'policy_db_modified.csv'))
        self.modified_coeffs_path = user_data_path(os.path.join('data', 'coefficients_modified.csv'))


    def _load_csv_with_encoding_fallback(self, filepath):
        """인코딩 폴백을 사용하여 CSV(쉼표 구분) 파일을 로드합니다."""
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='cp949')
        return df

    def _load_tsv_with_encoding_fallback(self, filepath):
        """인코딩 폴백을 사용하여 TSV(탭 구분) 파일을 로드합니다."""
        try:
            df = pd.read_csv(filepath, encoding='utf-8', sep='\t')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='cp949', sep='\t')
        return df

    def load_policy_data(self):
        """
        추진 과제(정책) 리스트를 로드합니다. (쉼표 구분)
        수정된 파일이 있으면 로드하고, 없으면 원본 파일을 로드합니다.
        """
        if os.path.exists(self.modified_policy_path):
            df = self._load_csv_with_encoding_fallback(self.modified_policy_path)
        else:
            df = self._load_csv_with_encoding_fallback(self.original_policy_path)
        
        df['duration_months'] = df['duration_months'].astype(str).str.replace('개월', '')
        df['duration_months'] = pd.to_numeric(df['duration_months'], errors='coerce').fillna(0).astype(int)
        return df

    def save_policy_data(self, df):
        """
        추진 과제(정책) 데이터프레임을 수정된 파일에 저장합니다 (항상 utf-8).
        """
        df.to_csv(self.modified_policy_path, index=False, encoding='utf-8')

    def load_coefficients_df(self):
        """
        계수 파일을 DataFrame 형태로 로드합니다. (탭 구분)
        수정된 파일이 있으면 로드하고, 없으면 원본 파일을 로드합니다.
        """
        if os.path.exists(self.modified_coeffs_path):
            df = self._load_tsv_with_encoding_fallback(self.modified_coeffs_path)
        else:
            df = self._load_tsv_with_encoding_fallback(self.original_coeffs_path)
        return df

    def load_coefficients(self):
        """ 만족도 모형 계수와 PAI, TCI 계수를 CSV에서 읽어 각각의 중첩 딕셔너리 구조로 변환합니다. """
        df = self.load_coefficients_df()
        # 'model_type' 열이 없으면 기본값 'A'로 추가
        if 'model_type' not in df.columns:
            df['model_type'] = 'A'

        coeffs = {"S_max": 10.0, "coefficients": {}}
        pai_coeffs = {'weights': {}, 'alpha': {}}
        tci_coeffs = {}

        for _, row in df.iterrows():
            rail_type = row['rail_type']
            kpi = row['kpi']
            model_type = row.get('model_type', 'A') # 이전 버전 호환성을 위해 기본값 'A'
            param1_name = row['param1_name']
            param1_value = row['param1_value']
            param2_name = row['param2_name']
            param2_value = row['param2_value']

            # PAI 가중치 및 알파 계수 분리
            if kpi == 'PAI':
                if param1_name.startswith('w_'):
                    mode_name = param1_name[2:]
                    if rail_type not in pai_coeffs['weights']:
                        pai_coeffs['weights'][rail_type] = {}
                    pai_coeffs['weights'][rail_type][mode_name] = float(param1_value)
                elif param1_name == 'alpha':
                    pai_coeffs['alpha'][rail_type] = float(param1_value)
            
            # TCI 계수 분리
            elif kpi == 'TCI':
                if rail_type not in tci_coeffs:
                    tci_coeffs[rail_type] = {'P': {}, 'c': {}}
                
                if param1_name == 'S_max':
                    tci_coeffs['S_max'] = float(param1_value)
                elif param1_name.startswith('P_'):
                    mode = param1_name[2:]
                    tci_coeffs[rail_type]['P'][mode] = float(param1_value)
                elif param1_name.startswith('c_'):
                    mode = param1_name[2:]
                    tci_coeffs[rail_type]['c'][mode] = float(param1_value)

            # --- 새로운 계수 데이터 구조 ---
            if rail_type not in coeffs['coefficients']:
                coeffs['coefficients'][rail_type] = {}
            if kpi not in coeffs['coefficients'][rail_type]:
                coeffs['coefficients'][rail_type][kpi] = {
                    'model_type': model_type,
                    'params': {}
                }
            
            # 파라미터 저장
            params_dict = coeffs['coefficients'][rail_type][kpi]['params']
            if pd.notna(param1_name) and pd.notna(param1_value):
                # TCI의 P, c 계수는 만족도 계산용이 아니므로 제외
                if not (kpi == 'TCI' and (param1_name.startswith('P_') or param1_name.startswith('c_'))):
                    params_dict[param1_name] = float(param1_value)
            if pd.notna(param2_name) and pd.notna(param2_value):
                params_dict[param2_name] = float(param2_value)

        # --- PAI 가중치 및 알파 하드코딩 ---
        # 사용자가 제공한 가중치를 여기에 직접 추가합니다.
        pai_coeffs['weights'] = {
            '고속철도': {
                '도보': 10.28, '택시': 26.64, '승용차': 20.56, '자전거': 0.47, 
                '공유PM': 0.47, '마을/시내버스': 18.22, '광역버스': 4.21, '지하철/광역철도': 19.16
            },
            '일반철도': {
                '도보': 5.97, '택시': 30.59, '승용차': 23.13, '자전거': 2.24, 
                '공유PM': 1.49, '마을/시내버스': 27.61, '광역버스': 5.22, '지하철/광역철도': 3.73
            },
            '광역철도': {
                '도보': 39.06, '택시': 9.67, '승용차': 6.81, '자전거': 5.38, 
                '공유PM': 3.58, '마을/시내버스': 23.66, '광역버스': 3.58, '지하철/광역철도': 8.24
            }
        }
        # 알파 값은 1.0으로 가정합니다.
        pai_coeffs['alpha'] = {
            '고속철도': 1.0,
            '일반철도': 1.0,
            '광역철도': 1.0
        }
        # ------------------------------------
                
        return coeffs, pai_coeffs, tci_coeffs
        
    def save_coefficients(self, df):
        """
        만족도 계수 데이터프레임을 수정된 파일에 저장합니다 (항상 utf-8).
        """
        df.to_csv(self.modified_coeffs_path, index=False, encoding='utf-8') # encoding 명시

    def restore_policy_data(self):
        """수정된 추진과제 파일만 삭제하여 원본 상태로 복원합니다."""
        try:
            if os.path.exists(self.modified_policy_path):
                os.remove(self.modified_policy_path)
                st.toast("✅ 추진 과제 데이터가 초기 상태로 복원되었습니다.")
            else:
                st.toast("ℹ️ 이미 초기 상태입니다.")
        except Exception as e:
            st.error(f"🚨 추진 과제 데이터 복원 중 오류 발생: {e}")

    def restore_coefficients_data(self):
        """수정된 계수 파일만 삭제하여 원본 상태로 복원합니다."""
        try:
            if os.path.exists(self.modified_coeffs_path):
                os.remove(self.modified_coeffs_path)
                st.toast("✅ 만족도 계수 데이터가 초기 상태로 복원되었습니다.")
            else:
                st.toast("ℹ️ 이미 초기 상태입니다.")
        except Exception as e:
            st.error(f"🚨 만족도 계수 데이터 복원 중 오류 발생: {e}")

    def restore_all_data(self):
        """수정된 모든 데이터 파일들을 삭제하여 원본 상태로 복원합니다."""
        try:
            files_removed = False
            if os.path.exists(self.modified_policy_path):
                os.remove(self.modified_policy_path)
                files_removed = True
            if os.path.exists(self.modified_coeffs_path):
                os.remove(self.modified_coeffs_path)
                files_removed = True
            
            if files_removed:
                st.toast("✅ 모든 데이터가 초기 상태로 복원되었습니다.")
            else:
                st.toast("ℹ️ 이미 모든 데이터가 초기 상태입니다.")
        except Exception as e:
            st.error(f"🚨 전체 데이터 복원 중 오류 발생: {e}")