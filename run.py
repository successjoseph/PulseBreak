"""
This is the new main entry point for PulseBreak.

It launches the PyQt UI (frontend/bubble.py) in the main thread
and the backend logic (backend/main.py) in a separate worker thread.
It also connects them so they can communicate.
"""

import sys
import os

# Add backend/ and frontend/ to the Python path
# This allows us to import 'main' and 'bubble'
script_dir = os.path.dirname(__file__)
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
    sys.exit(1)

# This class will hold our backend engine and run it on a separate thread
class BackendWorker(QObject):
    # --- Signals from Backend to Frontend ---
    # Signal to trigger a popup (sends title, message, type, duration)
    show_popup_signal = pyqtSignal(str, str, str, int)
    # Signal to trigger an audio cue (sends sound file name)
    play_audio_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # Create the engine instance
        self.engine = PulseBreakEngine()

        # --- FIX: Connect using dictionary key access ---
        # This "bridges" the engine's internal signals to our new class signals
        self.engine.app_state['signals'].show_popup.connect(self.show_popup_signal.emit)
        self.engine.app_state['signals'].play_audio.connect(self.play_audio_signal.emit)

        # Settings window is now handled within BubbleWidget
        # self.settings_window: SettingsWindow | None = None
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

    # --- on_settings_open_requested REMOVED ---
    # This is now handled directly by BubbleWidget

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
    # When UI bubble is quit -> tell worker to quit
    bubble_ui.quit_signal.connect(backend_worker.on_app_quit)
    # When UI mode is changed -> tell worker to change mode
    bubble_ui.mode_changed_signal.connect(backend_worker.on_mode_change_requested)
    # --- Settings signal connection REMOVED ---

    # --- Connect Backend Signals to Frontend Slots ---
    # When worker says show popup -> tell UI to show popup
    backend_worker.show_popup_signal.connect(bubble_ui.show_reminder_popup)

    # --- Load Data into UI ---
    # Get the modes from the config and give them to the UI
    modes = config.settings.get("modes", [])
    # Ensure active_mode_id exists, fall back to default if needed
    default_mode_id = "mode_001" # Fallback default
    for mode in modes:
        if mode.get("is_default"):
            default_mode_id = mode.get("id", default_mode_id)
            break
    current_mode_id = config.settings.get("active_mode_id", default_mode_id)

    bubble_ui.populate_modes(modes, current_mode_id)

    # --- Start Everything ---
    # Start the backend thread
    backend_thread.started.connect(backend_worker.run)
    backend_thread.start()

    # Show the UI
    bubble_ui.show()

    # Execute the application loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

