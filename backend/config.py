import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data"
SETTINGS_FILE = DATA_PATH / "settings.json"

DEFAULT_SETTINGS = {
    "break_interval_minutes": 20,
    "focus_mode": False
}

def load_settings():
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)

def save_settings(data):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)
