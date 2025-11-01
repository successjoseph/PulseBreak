"""
This is the new main entry point for PulseBreak.

It launches the PyQt UI (frontend/bubble.py) in the main thread
and the backend logic (backend/main.py) in a separate worker thread.
It also connects them so they can communicate.

It also now handles checking and setting the Windows startup registry
based on the "run_on_startup" setting in data/settings.json.
"""

import sys
import os
import winreg  # For Windows Registry startup tasks

# --- STARTUP REGISTRY CONFIG ---
# The name for the startup entry in the Windows Registry
APP_REGISTRY_NAME = "PulseBreak"
# The registry key for Current User startup programs
STARTUP_REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
# --- END STARTUP REGISTRY CONFIG ---


# Add backend/ and frontend/ to the Python path
# This allows us to import 'main' and 'bubble'
script_dir = os.path.dirname(os.path.abspath(__file__)) # Use absolute path
sys.path.append(os.path.join(script_dir, 'backend'))
sys.path.append(os.path.join(script_dir, 'frontend'))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QThread, pyqtSignal, QObject

# Import our UI and Backend
try:
    # BubbleWidget now contains SettingsPopup, no need for separate import
    from bubble import BubbleWidget            # type: ignore[import]
    from main import PulseBreakEngine          # type: ignore[import]
    import config                              # type: ignore[import]
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please make sure all files are in their correct 'backend' and 'frontend' folders.")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)


# --- STARTUP MANAGEMENT FUNCTIONS ---

def get_startup_command_and_path():
    """
    Determines the correct, absolute path and command to run the application,
    whether it's running as a .py script or a compiled .exe.
    
    Returns a tuple: (full_app_path, run_command)
    """
    try:
        # sys.frozen is set to True when running as a compiled executable (e.g., PyInstaller)
        if getattr(sys, 'frozen', False):
            # We are running as a compiled exe.
            # sys.executable is the path to the exe.
            app_path = sys.executable
            run_command = f'"{app_path}"'
            return app_path, run_command
        else:
            # We are running as a .py script.
            # sys.executable is the path to the python.exe.
            # __file__ is the path to this script (run.py).
            python_exe_path = sys.executable
            # Get absolute path to the currently running script (run.py)
            script_path = os.path.abspath(__file__) 
            run_command = f'"{python_exe_path}" "{script_path}"'
            return script_path, run_command
    except Exception as e:
        print(f"[Startup] Error determining app path: {e}")
        return None, None

def set_startup_registry(enable=True):
    """
    Modifies the Windows Registry to enable or disable startup.
    This function will not crash the app if it fails (e.g., permissions).
    
    :param enable: If True, adds/updates the startup entry. If False, removes it.
    """
    # Only run this on Windows
    if sys.platform != 'win32':
        print("[Startup] Skipping registry check: Not on Windows.")
        return

    app_path, run_command = get_startup_command_and_path()
    
    if not run_command:
        print("[Startup] Cannot modify registry: App path or command could not be determined.")
        return

    print(f"[Startup] Registry Name: {APP_REGISTRY_NAME}")
    print(f"[Startup] Registry Path: HKEY_CURRENT_USER\\{STARTUP_REG_KEY_PATH}")
    
    try:
        # Open the registry key. HKEY_CURRENT_USER is for the current user.
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            STARTUP_REG_KEY_PATH,
            0,
            winreg.KEY_ALL_ACCESS  # Request full access
        ) as key:
            
            if enable:
                # Set the value to register the app for startup
                winreg.SetValueEx(
                    key,
                    APP_REGISTRY_NAME,
                    0,
                    winreg.REG_SZ,  # REG_SZ means it's a string value
                    run_command
                )
                print(f"[Startup] Successfully REGISTERED '{APP_REGISTRY_NAME}' to run on startup.")
                print(f"[Startup] Command: {run_command}")
            else:
                # Delete the value to unregister the app
                try:
                    winreg.DeleteValue(key, APP_REGISTRY_NAME)
                    print(f"[Startup] Successfully UNREGISTERED '{APP_REGISTRY_NAME}' from startup.")
                except FileNotFoundError:
                    # This is not an error; it just means it was already unregistered.
                    print(f"[Startup] '{APP_REGISTRY_NAME}' was already unregistered from startup.")

    except PermissionError:
        print("\n--- [Startup] PERMISSION ERROR ---")
        print("[Startup] Could not modify the registry. Run as administrator if changes are needed.")
    except Exception as e:
        print(f"\n[Startup] An error occurred while accessing the registry: {e}")

def check_and_apply_startup_setting():
    """
    Reads the setting from the loaded config module and applies the registry change.
    """
    print("[Startup] Checking 'run_on_startup' setting...")
    try:
        # config.settings is already loaded by the 'import config' statement
        run_on_startup = config.settings.get("global_settings", {}).get("run_on_startup")
        
        if run_on_startup is True:
            print("[Startup] Setting is: True. Registering app...")
            set_startup_registry(enable=True)
        elif run_on_startup is False:
            print("[Startup] Setting is: False. Unregistering app...")
            set_startup_registry(enable=False)
        else:
            print(f"[Startup] Warning: 'run_on_startup' key not found or has an invalid value (value: {run_on_startup}).")
            print("[Startup] Expected a boolean (true/false) in global_settings.")

    except Exception as e:
        # This function should not crash the main app
        print(f"[Startup] An unexpected error occurred during startup check: {e}")

# --- END STARTUP MANAGEMENT FUNCTIONS ---


# This class will hold our backend engine and run it on a separate thread
class BackendWorker(QObject):
    # --- Signals from Backend to Frontend ---
    show_popup_signal = pyqtSignal(str, str, str, int)
    play_audio_signal = pyqtSignal(str)
    # --- NEW: Signal for TTS ---
    speak_text_signal = pyqtSignal(str, str)


    def __init__(self):
        super().__init__()
        # Create the engine instance
        self.engine = PulseBreakEngine()

        # Connect internal signals to our class signals
        self.engine.app_state['signals'].show_popup.connect(self.show_popup_signal.emit)
        self.engine.app_state['signals'].play_audio.connect(self.play_audio_signal.emit)
        # --- NEW: Connect TTS signal ---
        self.engine.app_state['signals'].speak_text.connect(self.speak_text_signal.emit)

        self.thread_ref: QThread | None = None # Store reference to the thread

    def run(self):
        """This method will be run in the new thread."""
        print("[Run.py] Starting backend engine in a separate thread...")
        self.engine.start_pulsebreak_engine()

    # --- Slots from Frontend to Backend ---
    def on_mode_change_requested(self, mode_id):
        """Receives signal from UI and tells engine to change mode."""
        print(f"[Run.py] Received mode change request from UI: {mode_id}")
        self.engine.set_current_mode(mode_id)

    def on_app_quit(self):
        """Receives signal from UI to quit the app."""
        print("[Run.py] Quitting application...")
        try:
            print("[Run.py] Telling engine to stop...")
            self.engine.stop_engine() # Tell the backend engine to stop gracefully first
        except Exception as e:
            print(f"[Run.py] Error stopping engine: {e}")

        # Force exit using os._exit which stops all threads immediately
        print("[Run.py] Forcing exit...")
        os._exit(0) # Forceful exit

    def set_thread(self, thread):
        """Stores a reference to the QThread this worker runs on."""
        self.thread_ref = thread


def main():
    # 1. Create the main application instance
    app = QApplication(sys.argv)
    
    # 1a. Check and apply startup registry settings
    # This runs after 'import config' has loaded the settings
    # and before the main UI loop starts.
    check_and_apply_startup_setting()

    # 2. Create the UI (Bubble)
    bubble_ui = BubbleWidget(app_instance=app)

    # 3. Create a thread for the backend
    backend_thread = QThread()
    # 4. Create our backend worker
    backend_worker = BackendWorker()
    # 5. Move the worker to the new thread
    backend_worker.moveToThread(backend_thread)
    # Give the worker a reference to its thread
    backend_worker.set_thread(backend_thread)


    # --- Connect Frontend Signals to Backend Slots ---
    bubble_ui.quit_signal.connect(backend_worker.on_app_quit)
    bubble_ui.mode_changed_signal.connect(backend_worker.on_mode_change_requested)

    # --- Connect Backend Signals to Frontend Slots ---
    backend_worker.show_popup_signal.connect(bubble_ui.show_reminder_popup)
    # --- NEW: Connect sound and TTS signals ---
    backend_worker.play_audio_signal.connect(bubble_ui.on_play_audio)
    backend_worker.speak_text_signal.connect(bubble_ui.on_speak_text)

    # --- Load Data into UI ---
    modes = config.settings.get("modes", [])
    default_mode_id = "mode_001" # Fallback default
    for mode in modes:
        if mode.get("is_default"):
            default_mode_id = mode.get("id", default_mode_id)
            break
    current_mode_id = config.settings.get("active_mode_id", default_mode_id)

    bubble_ui.populate_modes(modes, current_mode_id)

    # --- Start Everything ---
    backend_thread.started.connect(backend_worker.run)
    backend_thread.start()

    # Show the UI
    bubble_ui.show()

    # Execute the application loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

