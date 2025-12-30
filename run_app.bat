@echo off
chcp 65001 > nul
echo.
echo  ===============================================================
echo   Rail Indicator App (철도 성과지표 예측 및 정책 제안 시스템)
echo  ===============================================================
echo.
echo   잠시 후 Streamlit 서버가 실행되고 웹 브라우저에서 앱이 열립니다.
echo   이 콘솔 창을 닫으면 프로그램이 종료됩니다.
echo.

REM --- 가상환경이 있다면 여기서 활성화 하세요 ---
REM 예시: call .venv\Scripts\activate

REM --- Streamlit 앱 실행 ---
python -m streamlit.web.cli run m3.py

echo.
echo  프로그램이 종료되었습니다.
pause
