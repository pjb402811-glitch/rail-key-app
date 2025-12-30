# -*- coding: utf-8 -*-
# M2: 지표 예측 및 만족도 계산 모듈
import math
import pandas as pd
from m1 import DataManager # DataManager 임포트

def calculate_physical_tai(access_time, rail_type=None):
    """
    [수정됨] '시간적 접근성(TAI)'을 '역사 접근 시간' 기준으로 재계산합니다.
    - 입력: access_time (분 단위, 집에서 역까지 걸리는 시간)
    - 기준: 0분이면 100점, 60분 이상이면 0점 (선형 감소)
    """
    if access_time is None:
        return 0.0
    
    # =================================================================
    # [설정] 접근 시간 기준값 (단위: 분)
    # -----------------------------------------------------------------
    # ACCESS_MIN: 이 시간 이내면 만점 (예: 5분 역세권)
    # ACCESS_MAX: 이 시간을 넘으면 0점 (예: 60분)
    # =================================================================
    ACCESS_MIN = 5.0   
    ACCESS_MAX = 60.0  

    # 1. 범위 보정 (Min보다 작으면 Min으로, Max보다 크면 Max로)
    adjusted_time = max(ACCESS_MIN, min(ACCESS_MAX, float(access_time)))

    # 2. 선형 정규화 (Min-Max Normalization)
    # 시간이 짧을수록 점수가 높아야 하므로 (1 - 비율) 형태 사용
    denominator = ACCESS_MAX - ACCESS_MIN
    
    if denominator == 0:
        return 0.0
        
    normalized_score = 1.0 - ((adjusted_time - ACCESS_MIN) / denominator)

    # 3. 100점 만점 환산
    tai_value = normalized_score * 100.0

    return round(tai_value, 2)


def calculate_physical_eai(COST_access, COST_rail, COST_parking):
    """
    '경제적 접근성(EAI)'을 위해 사용자가 입력한 비용을 모두 더합니다.
    """
    # 입력값이 None이면 0으로 처리
    c1 = float(COST_access) if COST_access is not None else 0.0
    c2 = float(COST_rail) if COST_rail is not None else 0.0
    c3 = float(COST_parking) if COST_parking is not None else 0.0

    # [수정] 가중치(omega) 삭제 -> 단순 총 비용 합계 반환
    total_cost = c1 + c2 + c3
    
    return total_cost


def calculate_pai(selected_modes, weights, alpha):
    """
    '물리적 접근성(PAI)'의 물리적 지표 값을 계산합니다.
    """
    if not isinstance(selected_modes, list):
        return 0.0
        
    pai_value = sum(weights.get(mode, 0) for mode in selected_modes)
    return alpha * pai_value


def calculate_tci_score(distances, rail_type_coeffs, S_max):
    """
    '환승시설 편의성(TCI)'의 최종 만족도 점수를 사용자 제공 공식으로 직접 계산합니다.
    """
    sum_terms = 0
    
    if not isinstance(rail_type_coeffs, dict) or 'c' not in rail_type_coeffs or 'P' not in rail_type_coeffs:
        return 0.0

    C_coeffs = rail_type_coeffs.get('c', {})
    P_coeffs = rail_type_coeffs.get('P', {})

    for mode, distance in distances.items():
        c_j = C_coeffs.get(mode)
        P_j = P_coeffs.get(mode)

        if c_j is not None and P_j is not None and distance is not None:
            if distance == 0:
                mode_satisfaction_term = P_j * 1
            else:
                exp_component = math.exp(-c_j * (1 / distance))
                mode_satisfaction_term = P_j * (1 - exp_component)
            
            sum_terms += mode_satisfaction_term

    final_score = S_max * sum_terms
    final_score = min(10.0, max(0.0, final_score)) 
    
    return final_score


class SatisfactionCalculator:
    def __init__(self, config):
        self.config = config
        self.S_max = config['S_max']
        self.coefficients = config['coefficients']
        self.kpi_abbreviations = DataManager.KPI_ABBREVIATIONS

    def _get_kpi_config(self, rail_type, metric_name):
        kpi_abbr = self.kpi_abbreviations.get(metric_name, metric_name)
        
        if rail_type not in self.coefficients:
            raise ValueError(f"정의되지 않은 철도 유형: {rail_type}")
        if kpi_abbr not in self.coefficients[rail_type]:
            raise ValueError(f"'{rail_type}'에 대한 '{kpi_abbr}' 지표의 계수가 설정 파일에 없습니다.")
        
        return self.coefficients[rail_type][kpi_abbr]

    # --- Model A: 비선형 포화 모델 (기본값) ---
    def _calculate_model_a(self, value, params):
        c = params.get("c")
        if c is None:
            raise ValueError("Model A에 필요한 'c' 계수가 없습니다.")
        return self.S_max * (1 - math.exp(-c * value))

    def _reverse_model_a(self, score, params):
        c = params.get("c")
        if c is None:
            raise ValueError("Model A에 필요한 'c' 계수가 없습니다.")
        if score >= self.S_max: return float('inf')
        if score < 0: return 0.0
        try:
            ratio = min(score / self.S_max, 0.999999)
            return -math.log(1 - ratio) / c
        except (ValueError, ZeroDivisionError):
            return 0.0

    # --- Model B: S-자형 로지스틱 모델 ---
    def _calculate_model_b(self, value, params):
        """S(X) = S_max / (1 + e^(a * (X - X_0)))"""
        a = params.get("a")
        # '_0'으로 끝나는 키를 동적으로 찾습니다.
        x0 = next((v for k, v in params.items() if k.endswith('_0') or k == 'X_0'), None)

        if a is None or x0 is None:
            raise ValueError(f"Model B에 필요한 'a' 또는 'X_0' 형태의 계수가 없습니다. 전달된 파라미터: {params}")
        try:
            exp_term = math.exp(a * (value - x0))
        except OverflowError:
            return 0.0  # 에러 발생 시 멈추지 않고 0점 처리
        
        return self.S_max / (1 + exp_term)

    def _reverse_model_b(self, score, params):
        """X = (ln((S_max / S) - 1) / a) + X_0"""
        a = params.get("a")
        x0 = next((v for k, v in params.items() if k.endswith('_0') or k == 'X_0'), None)

        if a is None or x0 is None:
            raise ValueError(f"Model B에 필요한 'a' 또는 'X_0' 형태의 계수가 없습니다. 전달된 파라미터: {params}")

        if score <= 0: return float('inf')
        if score >= self.S_max: return 0.0
        try:
            ratio = max(self.S_max / score, 1.000001)
            return (math.log(ratio - 1) / a) + x0
        except (ValueError, ZeroDivisionError):
            return x0

    # [삭제됨] Model C 관련 함수 제거 완료

    def calculate_satisfaction(self, rail_type, metric_name, value):
        kpi_config = self._get_kpi_config(rail_type, metric_name)
        model_type = kpi_config.get('model_type', 'A') 
        params = kpi_config.get('params', {})

        score = 0.0
        
        # [수정됨] Model C 분기 삭제, B가 아니면 모두 A(기본값)로 처리
        if model_type == 'B':
            score = self._calculate_model_b(value, params)
        else: 
            # 설정파일에 'C'라고 적혀있어도 A로 계산되거나, 필요 시 에러 처리가 됨
            score = self._calculate_model_a(value, params)
            
        return round(score, 2)

    def reverse_calculate_value(self, rail_type, metric_name, score):
        score = max(0.0, min(self.S_max, score))
        kpi_config = self._get_kpi_config(rail_type, metric_name)
        model_type = kpi_config.get('model_type', 'A') 
        params = kpi_config.get('params', {})

        value = 0.0
        
        # [수정됨] Model C 분기 삭제
        if model_type == 'B':
            value = self._reverse_model_b(score, params)
        else: 
            value = self._reverse_model_a(score, params)
            
        return round(value, 2)

    def generate_sensitivity_table(self, rail_type, metric_name, current_value):
        # ... 기존 코드와 동일 ...
        ratios = [-0.2, -0.1, 0.0, 0.1, 0.2]
        labels = ["-20%", "-10%", "현재", "+10%", "+20%"]
        
        data = {}
        for label, r in zip(labels, ratios):
            new_val = current_value * (1 + r)
            new_val = max(0, new_val)
            new_score = self.calculate_satisfaction(rail_type, metric_name, new_val)
            data[label] = [f"{new_val:.2f}", f"{new_score:.2f}점"]
            
        df = pd.DataFrame(data, index=[metric_name, "만족도"])
        return df