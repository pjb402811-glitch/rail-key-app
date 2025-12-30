import os
import subprocess
import sys
import ctypes
import webbrowser
import time

def main():
    # 1. 경로 설정
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    python_exe = os.path.join(base_path, "python_embed", "python.exe")
    script_file = os.path.join(base_path, "m3.py")

    # 2. 안전장치 (파일 확인)
    if not os.path.exists(python_exe):
        ctypes.windll.user32.MessageBoxW(0, "python_embed 폴더 누락", "오류", 16)
        return
    if not os.path.exists(script_file):
        ctypes.windll.user32.MessageBoxW(0, "code/m3.py 파일 누락", "오류", 16)
        return

    # 3. Streamlit 실행 명령어 구성
    # --server.port 8501 : 포트를 8501로 고정 (브라우저가 주소를 알기 위해)
    # --server.headless true : Streamlit 자체의 브라우저 띄우기 기능은 끕니다 (우리가 직접 띄울 거니까)
    cmd = [
        python_exe, 
        "-m", "streamlit", 
        "run", script_file, 
        "--server.port", "8501",
        "--server.headless", "true",
        "--global.developmentMode", "false"
    ]

    # 4. [핵심 변경] 비동기 실행 (Popen)
    # subprocess.CREATE_NO_WINDOW : 하위 프로세스(Streamlit)의 검은 창을 숨김
    process = subprocess.Popen(
        cmd, 
        cwd=base_path, 
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    # 5. 서버가 켜질 때까지 잠시 대기 (2초)
    # 컴퓨터 속도에 따라 다르지만 보통 2~3초면 켜집니다.
    time.sleep(2)

    # 6. 브라우저 강제 오픈
    webbrowser.open("http://localhost:8501")

    # 7. 프로그램 유지
    # 사용자가 브라우저를 닫고 서버를 끌 때까지 런처도 꺼지면 안 됨
    process.wait()

if __name__ == "__main__":
    main()