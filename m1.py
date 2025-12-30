# -*- coding: utf-8 -*-
# M1: 데이터 매니저 (정책 DB 로드) - Streamlit Cloud 최적화 버전
import pandas as pd
import os
import streamlit as st

# --- [복구된 함수] 이 함수가 없어서 에러가 났습니다! ---
def resource_path(relative_path):
    """
    Streamlit Cloud 환경에서는 단순히 상대 경로를 반환하면 됩니다.
    """
    return relative_path

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
        # 1. 원본 파일 경로
        self.original_policy_path = "data/policy_db.csv"
        self.original_coeffs_path = "data/coefficients.csv"

        # 2. 수정 파일 경로
        self.modified_policy_path = "data/policy_db_modified.csv"
        self.modified_coeffs_path = "data/coefficients_modified.csv"

        # data 폴더가 혹시 없으면 생성
        if not os.path.exists('data'):
            os.makedirs('data')

    def _load_csv_with_encoding_fallback(self, filepath):
        if not os.path.exists(filepath):
            return None 

        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='cp949')
        return df

    def _load_tsv_with_encoding_fallback(self, filepath):
        if not os.path.exists(filepath):
            return None

        try:
            df = pd.read_csv(filepath, encoding='utf-8', sep='\t')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='cp949', sep='\t')
        return df

    def load_policy_data(self):
        if os.path.exists(self.modified_policy_path):
            df = self._load_csv_with_encoding_fallback(self.modified_policy_path)
        else:
            df = self._load_csv_with_encoding_fallback(self.original_policy_path)
        
        if df is None:
            # 파일이 없어도 앱이 죽지 않도록 빈 데이터프레임 반환
            return pd.DataFrame(columns=['category', 'name', 'cost', 'process', 'duration_months', 'related_kpi'])

        df['duration_months'] = df['duration_months'].astype(str).str.replace('개월', '')
        df['duration_months'] = pd.to_numeric(df['duration_months'], errors='coerce').fillna(0).astype(int)
        return df

    def save_policy_data(self, df):
        df.to_csv(self.modified_policy_path, index=False, encoding='utf-8')

    def load_coefficients_df(self):
        if os.path.exists(self.modified_coeffs_path):
            df = self._load_tsv_with_encoding_fallback(self.modified_coeffs_path)
        else:
            df = self._load_tsv_with_encoding_fallback(self.original_coeffs_path)
        
        if df is None:
            return pd.DataFrame() 

        return df

    def load_coefficients(self):
        df = self.load_coefficients_df()
        
        if df.empty:
            return {}, {}, {}

        if 'model_type' not in df.columns:
            df['model_type'] = 'A'

        coeffs = {"S_max": 10.0, "coefficients": {}}
        pai_coeffs = {'weights': {}, 'alpha': {}}
        tci_coeffs = {}

        for _, row in df.iterrows():
            rail_type = row['rail_type']
            kpi = row['kpi']
            model_type = row.get('model_type', 'A')
            param1_name = row['param1_name']
            param1_value = row['param1_value']
            param2_name = row['param2_name']
            param2_value = row['param2_value']

            if kpi == 'PAI':
                if str(param1_name).startswith('w_'):
                    mode_name = param1_name[2:]
                    if rail_type not in pai_coeffs['weights']:
                        pai_coeffs['weights'][rail_type] = {}
                    pai_coeffs['weights'][rail_type][mode_name] = float(param1_value)
                elif param1_name == 'alpha':
                    pai_coeffs['alpha'][rail_type] = float(param1_value)
            
            elif kpi == 'TCI':
                if rail_type not in tci_coeffs:
                    tci_coeffs[rail_type] = {'P': {}, 'c': {}}
                
                if param1_name == 'S_max':
                    tci_coeffs['S_max'] = float(param1_value)
                elif str(param1_name).startswith('P_'):
                    mode = param1_name[2:]
                    tci_coeffs[rail_type]['P'][mode] = float(param1_value)
                elif str(param1_name).startswith('c_'):
                    mode = param1_name[2:]
                    tci_coeffs[rail_type]['c'][mode] = float(param1_value)

            if rail_type not in coeffs['coefficients']:
                coeffs['coefficients'][rail_type] = {}
            if kpi not in coeffs['coefficients'][rail_type]:
                coeffs['coefficients'][rail_type][kpi] = {
                    'model_type': model_type,
                    'params': {}
                }
            
            params_dict = coeffs['coefficients'][rail_type][kpi]['params']
            if pd.notna(param1_name) and pd.notna(param1_value):
                if not (kpi == 'TCI' and (str(param1_name).startswith('P_') or str(param1_name).startswith('c_'))):
                    params_dict[param1_name] = float(param1_value)
            if pd.notna(param2_name) and pd.notna(param2_value):
                params_dict[param2_name] = float(param2_value)

        # 하드코딩된 PAI 가중치 (백업용)
        if not pai_coeffs['weights']:
             pai_coeffs['weights'] = {
                '고속철도': {'도보': 10.28, '택시': 26.64, '승용차': 20.56, '자전거': 0.47, '공유PM': 0.47, '마을/시내버스': 18.22, '광역버스': 4.21, '지하철/광역철도': 19.16},
                '일반철도': {'도보': 5.97, '택시': 30.59, '승용차': 23.13, '자전거': 2.24, '공유PM': 1.49, '마을/시내버스': 27.61, '광역버스': 5.22, '지하철/광역철도': 3.73},
                '광역철도': {'도보': 39.06, '택시': 9.67, '승용차': 6.81, '자전거': 5.38, '공유PM': 3.58, '마을/시내버스': 23.66, '광역버스': 3.58, '지하철/광역철도': 8.24}
            }
        if not pai_coeffs['alpha']:
            pai_coeffs['alpha'] = {'고속철도': 1.0, '일반철도': 1.0, '광역철도': 1.0}
                
        return coeffs, pai_coeffs, tci_coeffs
        
    def save_coefficients(self, df):
        df.to_csv(self.modified_coeffs_path, index=False, encoding='utf-8')

    def restore_all_data(self):
        try:
            if os.path.exists(self.modified_policy_path):
                os.remove(self.modified_policy_path)
            if os.path.exists(self.modified_coeffs_path):
                os.remove(self.modified_coeffs_path)
            st.toast("✅ 모든 데이터가 초기 상태로 복원되었습니다.")
        except Exception as e:
            st.error(f"🚨 복원 오류: {e}")