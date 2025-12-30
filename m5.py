# -*- coding: utf-8 -*-
# M6: PDF Report Generator
import base64
import io
import logging
import re
from datetime import datetime

class PdfGenerator:
    def _chart_to_base64_svg(self, chart) -> str:
        """Converts an Altair chart to a base64 encoded SVG string."""
        import altair as alt
        if chart is None:
            return None
        try:
            svg_io = io.StringIO()
            chart.save(svg_io, format='svg')
            svg_bytes = svg_io.getvalue().encode('utf-8')
            return base64.b64encode(svg_bytes).decode('utf-8')
        except Exception as e:
            logging.error(f"Altair 차트를 SVG로 변환하는 데 실패했습니다: {e}", exc_info=True)
            return None

    def generate_report(self, report_data: dict) -> bytes:
        """
        Generates a PDF report from the provided data, mimicking the web UI layout.
        """
        import pandas as pd
        from weasyprint import CSS, HTML
        
        # --- 데이터 추출 및 가공 ---
        kpi = report_data.get('target_kpi', 'N/A')
        unit = report_data.get('unit', '')

        # KPI별 입력값 레이블 정의
        kpi_labels = {
            "물리적 접근성": ("접근 교통수단", None),
            "시간적 접근성": ("운행거리 (km)", "소요시간 (시)"),
            "경제적 접근성": ("운행거리 (km)", "소요시간 (시)"),
            "환승시설 편의성": ("운행거리 (km)", "소요시간 (시)"),
            "운행횟수": ("운행횟수 (회/일)", None),
            "표정속도": ("운행거리 (km)", "소요시간 (분)"),
            "열차운행 정시성": ("정시운행률 (%)", None),
            "역사 시설 쾌적성": ("승하차인원 (명/시간)", "승강장 면적(㎡)"),
            "열차이용 쾌적성": ("재차인원 (명)", "공급량 (명)"),
            "환승시설 쾌적성": ("승하차인원 (명)", "환승통로 면적(㎡)"),
        }
        label1, label2 = kpi_labels.get(kpi, ("요소 1", "요소 2"))
        
        # 현재/미래 입력값 포매팅
        input_val_1 = report_data.get('input_val_1', 'N/A')
        input_val_2 = report_data.get('input_val_2', 'N/A')
        if kpi == '표정속도':
            input_val_2 = report_data.get('input_minute', 'N/A')
        
        future_input_val_1 = report_data.get('future_input_val_1', 'N/A')
        future_input_val_2 = report_data.get('future_input_val_2', 'N/A')
        if kpi == '표정속도':
            future_input_val_2 = report_data.get('future_input_minute', 'N/A')

        # --- KPI별 분석정보 HTML 블록 생성 ---
        current_kpi_info_html = ""
        future_kpi_info_html = ""
        if kpi == "물리적 접근성":
            current_modes = report_data.get('current_selected_modes', [])
            current_modes_str = ", ".join(current_modes) if current_modes else "선택된 항목 없음"
            current_kpi_info_html = f'''
                <div class="row">
                    <div class="column data-item" style="flex: none; width: 100%;">
                        <span class="data-label">접근 가능 교통수단</span>
                        <span class="data-value">{current_modes_str}</span>
                    </div>
                </div>
            '''
            
            future_modes = report_data.get('future_selected_modes', [])
            future_modes_str = ", ".join(future_modes) if future_modes else "선택된 항목 없음"
            future_kpi_info_html = f'''
                <div class="row">
                    <div class="column data-item" style="flex: none; width: 100%;">
                        <span class="data-label">접근 가능 교통수단</span>
                        <span class="data-value">{future_modes_str}</span>
                    </div>
                </div>
            '''
        else:
            current_kpi_info_html = f'''
                <div class="row">
                    <div class="column data-item"><span class="data-label">{label1}</span> <span class="data-value">{input_val_1}</span></div>
                    {'<div class="column data-item"><span class="data-label">' + str(label2) + '</span> <span class="data-value">' + str(input_val_2) + '</span></div>' if label2 else '<div class="column"></div>'}
                </div>
            '''
            future_kpi_info_html = f'''
                <div class="row">
                    <div class="column data-item"><span class="data-label">{label1}</span> <span class="data-value">{future_input_val_1}</span></div>
                    {'<div class="column data-item"><span class="data-label">' + str(label2) + '</span> <span class="data-value">' + str(future_input_val_2) + '</span></div>' if label2 else '<div class="column"></div>'}
                </div>
            '''

        # --- 나머지 데이터 가공 ---
        line_chart_svg = self._chart_to_base64_svg(report_data.get('line_chart'))
        timeline_chart_svg = self._chart_to_base64_svg(report_data.get('timeline_chart'))
        sens_df = report_data.get('sens_df', pd.DataFrame())
        sens_html = sens_df.to_html(classes='small-table sens-table', index=True, border=0) if not sens_df.empty else ""
        summary_df = report_data.get('summary_df', pd.DataFrame())
        summary_html = summary_df.to_html(classes='summary-table', header=False, border=0) if not summary_df.empty else ""
        
        active_policies_df = report_data.get('active_policies', pd.DataFrame())
        policies_html = "<p>선택된 추진 과제가 없습니다.</p>"
        if not active_policies_df.empty and 'active' in active_policies_df.columns:
            active_mask = active_policies_df['active']
            if active_mask.any():
                cols_to_show = ['category', 'name', 'cost', 'start_date_calc', 'duration_months_display']
                policies_to_display = active_policies_df.loc[active_mask, cols_to_show]
                policies_to_display.columns = ['분야', '추진 과제명', '추진 사업비', '추진 시작 시기', '추진 기간']
                policies_html = policies_to_display.to_html(classes='policy-table', index=False, border=0)

        analysis_message = ""
        if report_data.get('is_fail', False):
            analysis_message = f"""
            <div class="message-box error">
                🚨 분석 결과, 예측 만족도({report_data.get('future_predict_score', 0):.2f}점)가 
                목표 만족도({report_data.get('future_goal_score', 0):.2f}점)에 미달할 것입니다.
            </div>
            """
        else:
            analysis_message = f"""
            <div class="message-box success">
                ✅ 예측 만족도({report_data.get('future_predict_score', 0):.2f}점)가 
                목표 만족도({report_data.get('future_goal_score', 0):.2f}점)를 초과 달성했습니다.
            </div>
            """

        analysis_proposal_list = report_data.get('analysis_proposal', [])
        analysis_proposal_container_html = ""
        if analysis_proposal_list:
            html_texts = [re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text) for text in analysis_proposal_list]
            proposal_html_content = ""
            in_list = False
            for p in html_texts:
                is_list_item = p.strip().startswith('-')
                if is_list_item and not in_list:
                    proposal_html_content += "<ul>"
                    in_list = True
                elif not is_list_item and in_list:
                    proposal_html_content += "</ul>"
                    in_list = False
                if is_list_item:
                    list_item_text = p.strip()[1:].strip()
                    proposal_html_content += f"<li>{list_item_text}</li>"
                else:
                    proposal_html_content += f'<p class="summary-sentence">{p}</p>'
            if in_list:
                proposal_html_content += "</ul>"
            analysis_proposal_container_html = f"""
                <div style="page-break-inside: auto; margin-top: 20px;">
                    <h3 style="margin-bottom:15px;">다. 종합 분석 및 제언</h3>
                    {proposal_html_content}
                </div>
            """
        
        # --- 분석 대상 정보 HTML 블록 동적 생성 ---
        station_info_kpis = ["물리적 접근성", "시간적 접근성", "환승시설 편의성", "역사 시설 쾌적성", "환승시설 쾌적성"]
        
        analysis_target_html = ""
        if kpi in station_info_kpis:
            analysis_target_html = f'''
                <div class="row" style="margin-top:10px;">
                    <div class="column data-item"><span class="data-label">노선명</span> <span class="data-value">{report_data.get('line_name', 'N/A')}</span></div>
                    <div class="column data-item"><span class="data-label">역명</span> <span class="data-value">{report_data.get('station_name_input', 'N/A')}</span></div>
                </div>
            '''
        else:
            analysis_target_html = f'''
                <div class="row" style="margin-top:10px;">
                    <div class="column data-item"><span class="data-label">노선명(구간)</span> <span class="data-value">{report_data.get('line_name', 'N/A')} ({report_data.get('line_section_input', 'N/A')})</span></div>
                    <div class="column data-item"><span class="data-label">노선 길이(km)</span> <span class="data-value">{report_data.get('line_length_input', 'N/A')}</span></div>
                </div>
            '''

        html_template = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{ size: A4 portrait; margin: 1cm; }}
                body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; font-size: 9pt; line-height: 1.5; }}
                h1, h2, h3, p, div {{ margin: 0; padding: 0; }}
                h1 {{ font-size: 20pt; text-align: center; margin-top: 0cm; margin-bottom: 1cm; border-bottom: 2px solid #004a8f; padding-bottom: 0.3cm; }}
                h3 {{ font-size: 10pt; font-weight: bold; margin-bottom: 8px; page-break-after: avoid; }}
                p.summary-sentence {{ margin-bottom: 10px; font-size: 9pt; overflow-wrap: break-word; }}
                ul {{ padding-left: 20px; margin-top: 5px; margin-bottom: 10px; }}
                li {{ margin-bottom: 5px; overflow-wrap: break-word; }}
                .main-container {{ display: block; }}
                .row {{ display: flex; flex-direction: row; justify-content: space-between; gap: 10px; width: 100%; }}
                .column {{ flex: 1; }}
                .container-box {{ border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin-bottom: 20px; page-break-inside: avoid; }}
                .header-box {{ padding: 10px; border-radius: 5px; margin-bottom: 10px; font-weight: bold; font-size: 12pt;}}
                .blue-box {{ background-color: #e8f0fe; color: #1a73e8; border-left: 5px solid #1a73e8; }}
                .green-box {{ background-color: #e6f4ea; color: #137333; border-left: 5px solid #137333; }}
                .purple-box {{ background-color: #f3e8fd; color: #9334e6; border-left: 5px solid #9334e6; }}
                .data-item {{ background-color: #f9f9f9; border-radius: 4px; padding: 8px; font-size: 8.5pt; height: 100%; box-sizing: border-box;}}
                .data-label {{ font-weight: bold; color: #555; display: block; margin-bottom: 4px;}}
                .data-value {{ color: #111; }}
                table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
                th, td {{ border: 1px solid #ddd; padding: 5px; text-align: center; }}
                th {{ background-color: #f2f2f2; font-weight: bold; }}
                .summary-table td {{ font-weight: bold; }}
                .kpi-table th {{ width: 40%; text-align: left; padding-left: 8px; }}
                .kpi-table td {{ text-align: right; padding-right: 8px; }}
                .sens-table th:first-child {{ text-align: left; background-color: #f8f9fa; }}
                .policy-table th {{ text-align: center; }}
                .policy-table td {{ text-align: center; }}
                .policy-table td:nth-child(2) {{ text-align: left; }}
                .chart-container {{ text-align: center; margin-top: 10px; }}
                .chart-container img {{ max-width: 100%; height: auto; }}
                .message-box {{ padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 15px; font-weight: bold; }}
                .error {{ background-color: #fce8e6; color: #c5221f; }}
                .success {{ background-color: #e6f4ea; color: #137333; }}
            </style>
        </head>
        <body>
            <h1>철도 성과지표 분석 보고서</h1>
            <div class="main-container">
                <div class="row">
                    <div class="column">
                        <div class="container-box">
                            <div class="header-box blue-box">1. 현재 철도 현황</div>
                            <h3>가. 분석 대상 정보</h3>
                            <div class="row">
                                <div class="column data-item"><span class="data-label">분석할 성과지표</span> <span class="data-value">{kpi}</span></div>
                                <div class="column data-item"><span class="data-label">철도 유형</span> <span class="data-value">{report_data.get('rail_type', 'N/A')}</span></div>
                            </div>
                            {analysis_target_html}
                            <h3 style="margin-top:15px;">나. 성과지표 분석 정보</h3>
                            {current_kpi_info_html}
                            <h3 style="margin-top:15px;">다. 현재 성과지표</h3>
                            <p class="summary-sentence">
                                현재 <strong>{kpi}</strong>({report_data.get('current_val', 0):.1f}{unit})에 따른 국민 만족도는 
                                <strong>{report_data.get('current_score', 0):.1f}점</strong> (10점 만점) 입니다.
                            </p>
                            {sens_html}
                        </div>
                    </div>
                    <div class="column">
                        <div class="container-box">
                            <div class="header-box green-box">2. 미래 철도 상황</div>
                            <h3>가. 장래 목표연도</h3>
                            <div class="row">
                                <div class="column data-item" style="flex: none; width: 100%;"><span class="data-label">목표 시점</span> <span class="data-value">{report_data.get('target_year', 'N/A')}년 {report_data.get('target_month', 'N/A')}월</span></div>
                            </div>
                            <h3 style="margin-top:15px;">나. 철도 환경 변화 요소</h3>
                            {future_kpi_info_html}
                            <h3 style="margin-top:15px;">다. 장래 예측 및 목표</h3>
                            <div class="row">
                                <div class="column data-item"><span class="data-label">장래 목표 {kpi}</span> <span class="data-value">{report_data.get('future_goal_val', 0):.2f}{unit}</span></div>
                                <div class="column data-item"><span class="data-label">장래 목표 만족도</span> <span class="data-value">{report_data.get('future_goal_score', 0):.2f}점</span></div>
                            </div>
                            <div class="row" style="margin-top:10px;">
                                <div class="column data-item"><span class="data-label">장래 예측 {kpi}</span> <span class="data-value">{report_data.get('future_predict_val', 0):.2f}{unit}</span></div>
                                <div class="column data-item"><span class="data-label">장래 예측 만족도</span> <span class="data-value">{report_data.get('future_predict_score', 0):.2f}점</span></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="container-box">
                    <div class="header-box green-box">3. {kpi} 변화 추이 및 만족도 결과 요약</div>
                    {analysis_message}
                    <div class="row">
                        <div class="column">
                            <h3>가. 지표 변화 추이</h3>
                            <div class="chart-container">
                                {f'<img src="data:image/svg+xml;base64,{line_chart_svg}">' if line_chart_svg else '<p>차트 데이터가 없습니다.</p>'}
                            </div>
                        </div>
                        <div class="column">
                            <h3>나. 결과 요약</h3>
                            {summary_html}
                        </div>
                    </div>
                </div>
                <div class="container-box">
                    <div class="header-box purple-box">4. 추진과제 분석 결과 및 정책 수행 제언</div>
                    <h3>가. 추진 과제</h3>
                    {policies_html}
                    <h3 style="margin-top:15px;">나. 과제별 소요기간 그래프</h3>
                    <div class="chart-container">
                        {f'<img src="data:image/svg+xml;base64,{timeline_chart_svg}">' if timeline_chart_svg else ''}
                    </div>
                    {analysis_proposal_container_html}
                </div>
            </div>
        </body>
        </html>
        """
        
        return HTML(string=html_template).write_pdf()