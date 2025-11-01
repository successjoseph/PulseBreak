import json
import os
import sys
import platform
import getpass
from datetime import datetime

# --- +++ NEW: Path Configuration +++ ---
# Get the absolute path to the directory where run.py is (one level up from this file)
# This makes all paths reliable whether running from .py or .exe
# __file__ is config.py -> dirname is backend/ -> dirname is PulseBreak/
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, 'data')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')
LABELS_FILE = os.path.join(DATA_DIR, 'labeller.json')
THEMES_FILE = os.path.join(DATA_DIR, 'themes.json') # New themes file
# --- +++ END Path Configuration +++ ---


# --- Constants ---
VERSION = "0.3.0" # Version bump for theme support

# --- Default Settings Structure ---
DEFAULT_SETTINGS = {
    "version": VERSION,
    "first_run_timestamp": None,
    "system_info": {},
    
    # --- Global Settings ---
    "global_settings": {
        "run_on_startup": False,
        "enable_logging": True,
        "active_theme_id": "theme_obsidian_01", # <--- NEW: Last used theme
        "afk_threshold_sec": 300 # 5 minutes
    },
    
    # --- Reminder Library ---
    # Defines the default *content* for each reminder.
    "reminder_library": {
        "eye_break": {
            "name": "20-20-20 Eye Rule",
            "popup_message": "Time for an eye break!\nLook at something 20 feet (6m) away for 20 seconds.",
            "audio_cue": "chime.wav",
            "default_duration_sec": 20
        },
        "hydration": {
            "name": "Hydration",
            "popup_message": "Quick break!\nTime to drink some water and stay hydrated.",
            "audio_cue": "water_drop.wav",
            "default_duration_sec": 10
        },
        "stretch": {
            "name": "Move & Stretch",
            "popup_message": "Stand up, stretch your legs, and roll your shoulders.\nGet the blood flowing!",
            "audio_cue": "stretch_bell.wav",
            "default_duration_sec": 15
        },
        "posture": {
            "name": "Posture Check",
            "popup_message": "Posture Check!\nAre you sitting up straight? Shoulders back.",
            "audio_cue": "posture_ping.wav",
            "default_duration_sec": 5
        },
        "affirmation": {
            "name": "Mandatory Affirmation",
            "popup_message": "Time for your affirmation.\nTake a deep breath and speak your affirmation aloud.",
            "audio_cue": "affirmation_bell.wav",
            "default_duration_sec": 15
        }
    },
    
    # --- Affirmation Library ---
    "affirmation_library": [
        "I am focused and productive.",
        "I am calm and in control of my day.",
        "I value my health and well-being.",
        "Each break I take makes me more effective.",
        "I am capable of solving complex problems.",
        "I am creating positive habits.",
        "My work makes a difference."
    ],

    # --- Mode Definitions ---
    "modes": [
        {
            "id": "mode_001",
            "name": "At Work (Default)",
            "is_default": True,
            "reminders": {
                # Reminder key | enabled | interval | delivery | duration
                "eye_break":   { "enabled": True, "interval_min": 20, "delivery": "popup", "duration_sec": 20 },
                "hydration":   { "enabled": True, "interval_min": 60, "delivery": "popup", "duration_sec": 10 },
                "stretch":     { "enabled": True, "interval_min": 90, "delivery": "popup", "duration_sec": 15 },
                "posture":     { "enabled": False, "interval_min": 30, "delivery": "audio", "duration_sec": 5 },
                "affirmation": { "enabled": True, "interval_min": 120, "delivery": "popup", "duration_sec": 15 }
            }
        },
        {
            "id": "mode_002",
            "name": "Intense Focus",
            "is_default": False,
            "reminders": {
                "eye_break":   { "enabled": False, "interval_min": 20, "delivery": "popup", "duration_sec": 20 },
                "hydration":   { "enabled": True, "interval_min": 45, "delivery": "audio", "duration_sec": 10 },
                "stretch":     { "enabled": False, "interval_min": 90, "delivery": "popup", "duration_sec": 15 },
                "posture":     { "enabled": True, "interval_min": 15, "delivery": "audio", "duration_sec": 5 },
                "affirmation": { "enabled": True, "interval_min": 120, "delivery": "audio", "duration_sec": 15 }
            }
        }
    ]
}

# --- Helper Functions ---

def get_system_info():
    """Gathers basic system information for diagnostics."""
    try:
        username = getpass.getuser()
    except Exception:
        username = "unknown"
        
    return {
        "platform": sys.platform,
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "username": username
    }

def load_settings():
    """
    Loads settings from settings.json.
    If the file doesn't exist, creates it with default settings.
    """
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    try:
        with open(SETTINGS_FILE, 'r') as f:
            settings_data = json.load(f)
            # TODO: Add a migration check here if settings_data['version'] < VERSION
            print(f"Loaded settings from {SETTINGS_FILE}")
            return settings_data
            
    except FileNotFoundError:
        print(f"No settings file found. Creating new one at {SETTINGS_FILE}")
        try:
            # This is the user's first run
            new_settings = DEFAULT_SETTINGS
            new_settings["first_run_timestamp"] = datetime.now().isoformat()
            new_settings["system_info"] = get_system_info()
            
            save_settings(new_settings)
            return new_settings
        except Exception as e:
            print(f"CRITICAL: Could not create new settings file! {e}")
            return DEFAULT_SETTINGS # Return in-memory defaults
            
    except json.JSONDecodeError:
        print(f"CRITICAL: Settings file at {SETTINGS_FILE} is corrupt!")
        # TODO: Add a backup-and-restore logic
        print("Using default settings for this session.")
        return DEFAULT_SETTINGS # Return in-memory defaults

def save_settings(settings_data):
    """Saves the provided settings dictionary to settings.json."""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings_data, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

def load_labelled_apps():
    """
    Loads the list of 'work apps' from labeller.json.
    Returns an empty list if not found.
    """
    try:
        with open(LABELS_FILE, 'r') as f:
            work_apps = json.load(f)
            print(f"Loaded {len(work_apps)} work apps from {LABELS_FILE}")
            return work_apps
    except FileNotFoundError:
        print(f"No {LABELS_FILE} found. No 'work apps' will be tracked.")
        return []
    except json.JSONDecodeError:
        print(f"Error reading {LABELS_FILE}. File might be corrupt.")
        return []

# --- Main Exported Settings ---
# This is the single object the rest of our app will import.
# 1. Load the main settings from settings.json
settings = load_settings()

# 2. Load the work apps from labeller.json
# 3. Inject the work apps list into the main settings object
#    This ensures it's always up-to-date on startup.
settings['work_apps'] = load_labelled_apps() 

# --- Self-Test ---
if __name__ == "__main__":
    print("--- PulseBreak Configuration Loaded ---")
    print(f"Version: {settings.get('version')}")
    print(f"User: {settings.get('system_info', {}).get('username')}")
    print(f"Theme: {settings.get('global_settings', {}).get('active_theme_id')}")
    print(f"Tracking {len(settings.get('work_apps', []))} work apps.")
    print(f"Loaded {len(settings.get('modes', []))} modes.")
    print(f"Settings file path: {SETTINGS_FILE}")
    print(f"Themes file path: {THEMES_FILE}")

