# -*- coding: utf-8 -*-
# M6: 설문조사 결과 기반 계수 산출 모듈

import pandas as pd
import numpy as np
from scipy.optimize import curve_fit
import streamlit as st
from m1 import DataManager
import os
import math

class SurveyAnalyzer:
    def __init__(self):
        self.dm = DataManager()
        self.kpi_abbreviations = self.dm.KPI_ABBREVIATIONS
        self.s_max = 10.0 # 만족도 점수의 최대값 (고정)

    # --- 만족도 모델 함수 정의 ---
    # Model A: S(X) = S_max * (1 - exp(-c * X))
    def _model_a(self, X, c):
        # 오버플로우 방지를 위해 np.exp에 클리핑 적용 가능하나, 보통 c가 작아서 괜찮음
        return self.s_max * (1 - np.exp(-c * X))

    # Model C: S(X) = S_max * exp(-c * X)
    def _model_c(self, X, c):
        return self.s_max * np.exp(-c * X)

    def _fit_model(self, X_data, S_data, model_func, initial_guesses, bounds=None):
        """주어진 데이터를 사용하여 모델의 계수를 피팅합니다."""
        try:
            # maxfev를 늘려 복잡한 피팅도 시도
            if bounds:
                popt, pcov = curve_fit(model_func, X_data, S_data, p0=initial_guesses, bounds=bounds, maxfev=10000)
            else:
                popt, pcov = curve_fit(model_func, X_data, S_data, p0=initial_guesses, maxfev=10000)
            return popt
        except RuntimeError as e:
            st.error(f"모델 피팅 실패(수렴하지 않음): {e}")
            return None
        except ValueError as e:
            st.error(f"모델 피팅 값 오류: {e}")
            return None

    def calculate_coefficients(self, rail_type, kpi_name_kor, survey_df, model_type, original_filename=None):
        """
        설문조사 데이터를 기반으로 계수를 산출합니다.
        [수정] 경제적 접근성(고속/일반)은 '만원' 단위로 변환하여 계산
        [수정] Model B는 평균값을 X0로 고정
        """
        # 1. 데이터 준비
        X_data = survey_df['kpi_value'].values.astype(float)
        S_data = survey_df['satisfaction_score'].values.astype(float)

        if len(X_data) < 2:
            st.warning(f"데이터 포인트가 부족합니다. (최소 2개 필요)")
            return pd.DataFrame(), None
        
        kpi_abbr = self.kpi_abbreviations.get(kpi_name_kor, kpi_name_kor)
        
        # 2. [핵심 수정] 단위 변환 (원 -> 만원)
        # 경제적 접근성이며 고속/일반철도인 경우 스케일링 적용
        scale_factor = 1.0
        if kpi_abbr == "EAI" and rail_type in ["고속철도", "일반철도"]:
            scale_factor = 10000.0
            X_data = X_data / scale_factor
            st.info(f"💡 '{kpi_name_kor}({rail_type})' 분석을 위해 데이터를 '만원' 단위로 변환하여 계산합니다. (나누기 10,000)")

        params_found = None
        model_func = None
        popt = None
        stats = None

        try:
            if kpi_abbr == "TCI":
                st.warning("TCI는 별도 산출 방식이 필요합니다.")
                return pd.DataFrame(), None

            # 3. 모델별 피팅 로직
            if model_type == 'A':
                model_func = self._model_a
                initial_guesses = [0.01] 
                bounds = ([0.], [np.inf])
                popt = self._fit_model(X_data, S_data, model_func, initial_guesses, bounds)
                if popt is not None:
                    params_found = {'c': popt[0]}
            
            elif model_type == 'B':
                # [핵심 수정] X0(변곡점)를 데이터의 '평균값'으로 고정!
                avg_X = np.mean(X_data)
                st.write(f"📊 **데이터 평균값(변곡점 기준)**: {avg_X:.4f} (단위 변환 적용됨)")

                # 고정된 X0를 사용하는 내부 함수 정의
                def _model_b_fixed_x0(x, a):
                    # a가 양수여야 비용 증가 시 만족도 하락 (분모 커짐)
                    # S = S_max / (1 + exp(a * (x - avg_X)))
                    try:
                        # overflow 방지: 지수승이 너무 크면 700 정도로 제한
                        val = a * (x - avg_X)
                        val = np.clip(val, -700, 700) 
                        return self.s_max / (1 + np.exp(val))
                    except Exception:
                        return 0.0

                # 기울기(a)만 추정하면 됨
                initial_guesses = [0.5] 
                bounds = ([0], [np.inf]) # a > 0
                
                popt = self._fit_model(X_data, S_data, _model_b_fixed_x0, initial_guesses, bounds)
                
                if popt is not None:
                    # 결과 저장 시 X0는 고정했던 평균값(avg_X)을 사용
                    params_found = {'a': popt[0], f'{kpi_abbr}_0': avg_X}
            
            elif model_type == 'C':
                model_func = self._model_c
                initial_guesses = [0.001]
                bounds = ([0.], [np.inf])
                popt = self._fit_model(X_data, S_data, model_func, initial_guesses, bounds)
                if popt is not None:
                    params_found = {'c': popt[0]}
            
            else:
                st.error(f"알 수 없는 모델 타입: {model_type}")
                return pd.DataFrame(), None

            # 4. 결과 정리 및 저장
            if params_found:
                # 통계치 계산을 위한 예측값 생성 (Model B는 별도 함수 사용)
                if model_type == 'B':
                    def _final_model_b(x, a, x0):
                        val = np.clip(a * (x - x0), -700, 700)
                        return self.s_max / (1 + np.exp(val))
                    s_pred = _final_model_b(X_data, params_found['a'], params_found[f'{kpi_abbr}_0'])
                else:
                    s_pred = model_func(X_data, *popt)

                sse = np.sum((S_data - s_pred) ** 2)
                sst = np.sum((S_data - np.mean(S_data)) ** 2)
                r_squared = 1 - (sse / sst) if sst > 0 else 0
                stats = { "SSE": sse, "SST": sst, "R-squared": r_squared }

                # 결과 텍스트 파일 저장
                if original_filename:
                    result_text = [
                        f"1. 입력 파일명: {original_filename}",
                        f"2. 분석 성과지표: {kpi_name_kor} ({rail_type})",
                        f"3. 적용 모델: Model {model_type}",
                        "\n4. 분석 결과",
                        f" - 산출 계수: {', '.join([f'{name}={val:.6f}' for name, val in params_found.items()])}",
                        f" - SSE: {stats['SSE']:.4f}",
                        f" - R-squared: {stats['R-squared']:.4f}",
                        f" - (참고) 적용된 단위 스케일: 1/{scale_factor}"
                    ]
                    output_filename = f"{os.path.splitext(original_filename)[0]}_result.txt"
                    with open(output_filename, 'w', encoding='utf-8') as f:
                        f.write("\n".join(result_text))
                    st.info(f"✅ 결과 저장 완료: {output_filename}")

                # DataFrame 반환용 데이터 생성
                df_rows = []
                param_items = list(params_found.items())
                row = {
                    'rail_type': rail_type,
                    'kpi': kpi_abbr,
                    'model_type': model_type,
                    'param1_name': param_items[0][0],
                    'param1_value': param_items[0][1],
                    'param2_name': param_items[1][0] if len(param_items) > 1 else None,
                    'param2_value': param_items[1][1] if len(param_items) > 1 else None,
                }
                df_rows.append(row)
                return pd.DataFrame(df_rows), stats
            
            else:
                st.warning("계수 산출 실패")
                return pd.DataFrame(), None

        except Exception as e:
            st.error(f"오류 발생: {e}")
            return pd.DataFrame(), None