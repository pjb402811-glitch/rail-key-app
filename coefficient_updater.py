# -*- coding: utf-8 -*-
"""
'data/coefficients.csv' 파일을 읽고, 각 행에 지정된 조건에 따라
'mini' 폴더의 해당 데이터 파일을 분석하여, 산출된 모델 계수를
다시 'data/coefficients.csv'에 업데이트하는 스크립트.
"""
import os
import pandas as pd
import numpy as np
from scipy.optimize import curve_fit

# --- 상수 정의 ---
# mini/coefficient_analyzer.py 와 동일한 로직을 가져옴
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, 'data')
MINI_DIR = os.path.join(SCRIPT_DIR, 'mini')
COEFF_FILE_PATH = os.path.join(DATA_DIR, 'coefficients.csv')

# --- SurveyAnalyzer 클래스 및 관련 딕셔너리 ---
# mini/coefficient_analyzer.py 에서 클래스와 딕셔너리를 가져와서 재사용
KPI_ABBREVIATIONS = {
    "물리적 접근성": "PAI", "시간적 접근성": "TAI", "경제적 접근성": "EAI",
    "운행횟수": "TF", "표정속도": "Tv", "열차운행 정시성": "TOtP",
    "환승시설 편의성": "TCI", "역사 시설 쾌적성": "SC", "열차이용 쾌적성": "TC",
    "환승시설 쾌적성": "TPC"
}

RAIL_TYPE_CODE_MAP = {
    "고속철도": "H",
    "일반철도": "L",
    "광역철도": "W"
}

class SurveyAnalyzer:
    def __init__(self):
        self.kpi_abbreviations = KPI_ABBREVIATIONS
        self.s_max = 10.0

    def _model_a(self, X, c, X0): return self.s_max * (1 - np.exp(-c * (X - X0)))
    def _model_b(self, X, a, X0): return self.s_max / (1 + np.exp(a * (X - X0)))
    def _model_c(self, X, c): return self.s_max * np.exp(-c * X)

    def _fit_model(self, X_data, S_data, model_func, initial_guesses, bounds=None):
        try:
            popt, _ = curve_fit(model_func, X_data, S_data, p0=initial_guesses, bounds=bounds, maxfev=5000)
            return popt
        except (RuntimeError, ValueError):
            return None

    def calculate_single_model(self, survey_df, kpi_abbr, model_type):
        # Ensure data is numeric, coercing errors to NaN and then dropping them
        survey_df['KPI'] = pd.to_numeric(survey_df['KPI'], errors='coerce')
        survey_df['Satisfaction'] = pd.to_numeric(survey_df['Satisfaction'], errors='coerce')
        survey_df.dropna(subset=['KPI', 'Satisfaction'], inplace=True)
        
        X_data = survey_df['KPI'].values
        S_data = survey_df['Satisfaction'].values

        if len(X_data) < 3:
            return None

        model_func, popt, params_found = None, None, None
        
        # 모델 타입에 따라 분기
        if model_type == 'A':
            model_func = self._model_a
            initial_guesses = [0.1, np.median(X_data)] 
            bounds = ([0, X_data.min()], [np.inf, X_data.max()])
            popt = self._fit_model(X_data, S_data, model_func, initial_guesses, bounds)
            if popt is not None: params_found = {'c': popt[0], f'{kpi_abbr}_0': popt[1]}
        elif model_type == 'B':
            model_func = self._model_b
            popt = self._fit_model(X_data, S_data, model_func, [0.1, np.median(X_data)], ([0, X_data.min()], [np.inf, X_data.max()]))
            if popt is not None: params_found = {'a': popt[0], f'{kpi_abbr}_0': popt[1]}
        elif model_type == 'C':
            model_func = self._model_c
            popt = self._fit_model(X_data, S_data, model_func, [0.001], ([0.], [np.inf]))
            if popt is not None: params_found = {'c': popt[0]}

        if params_found:
            s_pred = model_func(X_data, *popt)
            sse = np.sum((S_data - s_pred) ** 2)
            sst = np.sum((S_data - np.mean(S_data)) ** 2)
            r_squared = 1 - (sse / sst) if sst > 0 else 0
            stats = {"R-squared": r_squared}
            return {'params': params_found, 'stats': stats}
        return None

def update_coefficients():
    """
    coefficients.csv 파일을 읽고, 각 행에 대해 분석을 수행한 후,
    계산된 파라미터로 다시 파일을 업데이트합니다.
    """
    try:
        # The CSV file is actually tab-separated, so specify sep='\t'
        coeffs_df = pd.read_csv(COEFF_FILE_PATH, encoding='cp949', sep='\t')
    except FileNotFoundError:
        print(f"🚨 오류: '{COEFF_FILE_PATH}' 파일을 찾을 수 없습니다.")
        return

    # R_squared 열이 없으면 추가
    if 'R_squared' not in coeffs_df.columns:
        coeffs_df['R_squared'] = np.nan

    analyzer = SurveyAnalyzer()
    print("🚀 계수 업데이트를 시작합니다...")

    # DataFrame 복사본을 만들어 순회 중 변경사항이 원본에 영향을 주지 않도록 함
    for index, row in coeffs_df.copy().iterrows():
        rail_type = row['rail_type']
        kpi = row['kpi']
        model_type = row['model_type']

        # 소스 데이터 파일 이름 구성
        rail_code = RAIL_TYPE_CODE_MAP.get(rail_type)
        if not rail_code:
            print(f"⚠️ 경고: '{rail_type}'에 해당하는 철도 코드를 찾을 수 없습니다. (행 {index+2})")
            continue
        
        source_filename = f"{kpi}_{rail_code}.csv"
        source_filepath = os.path.join(MINI_DIR, source_filename)

        if not os.path.exists(source_filepath):
            # 'TV' -> 'Tv' 같은 대소문자 변형 시도
            if kpi.lower() != kpi:
                source_filename_lower = f"{kpi.lower()}_{rail_code}.csv"
                source_filepath_lower = os.path.join(MINI_DIR, source_filename_lower)
                if os.path.exists(source_filepath_lower):
                    source_filepath = source_filepath_lower
                else:
                    print(f"⚠️ 경고: 소스 데이터 파일 '{source_filename}' 또는 '{source_filename_lower}'을(를) 찾을 수 없습니다. (행 {index+2})")
                    continue
            else:
                print(f"⚠️ 경고: 소스 데이터 파일 '{source_filename}'을(를) 찾을 수 없습니다. (행 {index+2})")
                continue
        
        try:
            survey_df = pd.read_csv(source_filepath)
            if 'KPI' not in survey_df.columns or 'Satisfaction' not in survey_df.columns:
                 print(f"⚠️ 경고: '{source_filepath}'에 'KPI' 또는 'Satisfaction' 열이 없습니다. (행 {index+2})")
                 continue
        except Exception as e:
            print(f"🚨 오류: '{source_filepath}' 파일 읽기 중 오류 발생: {e} (행 {index+2})")
            continue

        # 분석 수행
        result = analyzer.calculate_single_model(survey_df, kpi, model_type)

        if result and 'params' in result and 'stats' in result:
            params = result['params']
            stats = result['stats']
            r_squared = stats['R-squared']
            print(f"✅ 분석 완료: {rail_type}-{kpi} | 모델: {model_type} | R²: {r_squared:.4f} | 결과: {params}")

            # 파라미터 업데이트
            param1_name = row['param1_name']
            if param1_name in params:
                coeffs_df.loc[index, 'param1_value'] = params[param1_name]
            
            param2_name = row['param2_name']
            if param2_name in params:
                coeffs_df.loc[index, 'param2_value'] = params[param2_name]
            
            # R-squared 값 업데이트
            coeffs_df.loc[index, 'R_squared'] = r_squared
        else:
            print(f"❌ 분석 실패: {rail_type}-{kpi} | 모델: {model_type} | 계수를 산출할 수 없습니다.")

    # 업데이트된 DataFrame을 CSV 파일로 저장
    try:
        # UTF-8 with BOM으로 저장하여 Excel에서 한글이 깨지지 않도록 함
        coeffs_df.to_csv(COEFF_FILE_PATH, index=False, encoding='utf-8-sig')
        print(f"\n🎉 모든 계수 업데이트가 완료되었습니다. 결과가 '{COEFF_FILE_PATH}'에 저장되었습니다.")
    except Exception as e:
        print(f"🚨 오류: 최종 CSV 파일 저장 중 오류 발생: {e}")


if __name__ == "__main__":
    update_coefficients()
