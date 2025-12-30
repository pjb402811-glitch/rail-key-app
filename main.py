import sys
import os
import multiprocessing
import time # Added for time.sleep
import traceback # Added for printing full traceback

import socket

def find_free_port():
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# --- Add GTK to DLL search path (for WeasyPrint) ---
# This ensures that the GTK DLLs are found when running from source (e.g., in VS Code)
# or when packaged. This is the recommended way for Python 3.8+ on Windows.
if sys.platform == "win32" and hasattr(os, 'add_dll_directory'):
    gtk_bin_path = resource_path(os.path.join('gtk_runtime', 'bin'))
    if os.path.isdir(gtk_bin_path):
        os.add_dll_directory(gtk_bin_path)

if __name__ == '__main__':
    multiprocessing.freeze_support()

    # --- Debugging prints ---
    print("--- Starting RailIndicatorApp Launcher ---")
    print(f"Python executable: {sys.executable}")
    print(f"sys.path: {sys.path}")
    print(f"Current working directory: {os.getcwd()}")
    # --- End debugging prints ---

    try:
        # Import Streamlit's CLI runner
        from streamlit.web import cli as stcli

        # Get the path to the actual Streamlit script
        streamlit_script_path = resource_path('m3.py')

        # --- Debugging: Check if Streamlit script exists ---
        if not os.path.exists(streamlit_script_path):
            print(f"Error: Streamlit script not found at {streamlit_script_path}")
            sys.exit(1)
        print(f"Streamlit script path: {streamlit_script_path}")
        # --- End debugging ---

        # Find a free port
        port = find_free_port()
        print(f"Using available port: {port}")

        # This is the crucial part: we are faking the command-line arguments
        # that the 'streamlit' command would normally receive.
        # We enforce the dynamically found port to avoid conflicts.
        sys.argv = [
            "streamlit",
            "run",
            streamlit_script_path,
            "--server.port", str(port),
            "--server.headless", "true",
        ]

        # We then call Streamlit's main function directly.
        stcli.main()

    except BaseException as e:
        print("--- AN ERROR OCCURRED IN THE LAUNCHER ---")
        print(f"Error Type: {type(e)}")
        print(f"Error Details: {e}")
        traceback.print_exc() # Print full traceback for more details
    finally:
        print("\n--- Launcher has finished or encountered an error. ---")
        print("--- Keeping window open for 10 seconds to read messages ---")
        time.sleep(10) # Keep console window open for 10 seconds
        print("--- Exiting ---")