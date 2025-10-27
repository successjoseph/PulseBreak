"""
This file contains all the helper functions for the backend.
It now returns 4 values for reminder content.
"""

import sys
import psutil
import random

# Import our loaded settings from config.py
try:
    import config
except ImportError:
    # Handle the case where this file is imported before the path is set
    print("Warning: config.py not found in functions.py. This is normal on first import.")
    # FIX: Define a fallback config object to satisfy Pylance
    class FallbackConfig:
        settings = {}
    config = FallbackConfig()

if sys.platform == 'win32':
    import win32gui
    import win32process
else:
    print(f"Warning: Active window detection not implemented for {sys.platform}")

# --- Core App Logic ---

def get_active_window_process_name():
    """
    Returns the process name (e.g., "chrome.exe") of the
    currently active foreground window.
    """
    if sys.platform == 'win32':
        try:
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            return process.name()
        except Exception as e:
            return None
    else:
        return "unsupported_os"

def is_work_app_active():
    """
    Checks if the currently active window's process
    is in the user's defined list of "work apps" from config.
    """
    # config.settings might not be loaded on the very first import,
    # so we use .get() for safety.
    work_apps_list = config.settings.get("work_apps", []) 
    
    active_app = get_active_window_process_name()
    
    if active_app and active_app.lower() in [app.lower() for app in work_apps_list]:
        return True
    return False

# --- Reminder Content ---

def get_reminder_content(reminder_id):
    """
    Fetches the content for a specific reminder.
    Returns: (title, message, audio_cue, duration_sec)
    """
    # Get the library item for this reminder
    lib_item = config.settings.get("reminder_library", {}).get(reminder_id, {})
    
    title = lib_item.get("name", "PulseBreak Reminder")
    message = lib_item.get("popup_message", "Time for a break!")
    audio_cue = lib_item.get("audio_cue", "chime.wav")
    
    # --- FIX: Return all 4 values ---
    duration_sec = lib_item.get("duration_sec", 5) # Default to 5 seconds

    # If it's an affirmation, pick a random one
    if reminder_id == "affirmation":
        affirm_list = config.settings.get("affirmation_library", [])
        if affirm_list:
            # Pick a random affirmation and add it to the message
            random_affirmation = random.choice(affirm_list)
            message = f"{message}\n\n\"{random_affirmation}\""
        else:
            message = f"{message}\n\n\"(You have no affirmations in your library.)\""

    return title, message, audio_cue, duration_sec

