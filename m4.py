# -*- coding: utf-8 -*-
# M5: 정책 제안 및 타임라인 생성기
import pandas as pd
from dateutil.relativedelta import relativedelta
from datetime import datetime

class ProjectRecommender:
    def create_timeline_data(self, policy_df, target_year, target_month):
        """
        목표 연도/월을 기준으로 각 정책의 시작일을 역산합니다.
        """
        # [수정] 목표 시점을 목표월의 다음달 1일로 설정하여 기간 계산 오류 수정
        # 이렇게 하면, 1개월 기간의 프로젝트가 해당 월의 1일부터 말일까지 정확히 채워짐
        end_point = datetime(target_year, target_month, 1) + relativedelta(months=1)
        
        timeline_data = []
        
        for _, row in policy_df.iterrows():
            duration = int(row['duration_months'])
            # 역산: 종료 시점 - 소요 기간
            start_date = end_point - relativedelta(months=duration)
            
            timeline_data.append({
                "Project": row['name'],
                "Category": row['category'],
                "Start": start_date,
                "End": end_point, # 모든 프로젝트가 같은 시점에 끝나도록 설정
                "Duration": f"{duration}개월",
                "Cost": row['cost']
            })
            
        return pd.DataFrame(timeline_data)