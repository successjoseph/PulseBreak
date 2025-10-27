"""
This is the backend engine.
It is now designed to be run in a separate thread from the UI.
It no longer prints directly, but emits signals.
"""

import sys
import time
from apscheduler.schedulers.background import BackgroundScheduler
from PyQt6.QtCore import QObject, pyqtSignal

# Import from our other backend files
try:
    import config
    import functions as fn
except ImportError:
    print("Error: Could not import config.py or functions.py")
    sys.exit(1)


# --- Signal Emitter Class ---
# We create a simple QObject to hold our signals.
# This allows main.py to send signals to run.py
class EngineSignals(QObject):
    # FIX: Add 'int' for the duration
    # Signal(title, message, type, duration_sec)
    show_popup = pyqtSignal(str, str, str, int)
    # Signal(str) -> (sound_file_name)
    play_audio = pyqtSignal(str)

# --- Main Engine Class ---
class PulseBreakEngine(QObject):
    def __init__(self):
        super().__init__()
        self.app_state = {
            "scheduler": BackgroundScheduler(),
            "current_mode_id": None,
            "is_work_app_active": False,
            "is_afk": False,
            "last_active_time": time.time(),
            "signals": EngineSignals() # Add the signal emitter
        }

    def trigger_scheduled_reminder(self, reminder_id):
        """
        This function is called by the scheduler.
        It checks if the reminder should be fired or skipped.
        """
        print(f"[Engine] Scheduler trying to fire '{reminder_id}'...")
        
        # 1. Check for AFK
        if self.app_state['is_afk']:
            print(f"[Engine] SKIP: User is AFK.")
            return

        # 2. Check for Work App
        if not self.app_state['is_work_app_active']:
            print(f"[Engine] SKIP: Work app is not active.")
            return

        # --- If checks pass, fire the reminder ---
        print(f"[Engine] FIRING '{reminder_id}'")
        
        # Get all modes and the current mode's settings
        modes = config.settings.get("modes", [])
        current_mode = next((m for m in modes if m['id'] == self.app_state['current_mode_id']), None)
        if not current_mode:
            return # Should not happen

        reminder_settings = current_mode['reminders'].get(reminder_id, {})
        delivery_type = reminder_settings.get("delivery", "popup")

        # --- Call the appropriate function ---
        # FIX: Now returns duration
        title, message, audio_cue, duration_sec = fn.get_reminder_content(reminder_id)
        
        if delivery_type == "popup":
            # EMIT a signal instead of printing
            # FIX: Use dot notation and send all 4 args
            self.app_state["signals"].show_popup.emit(title, message, "popup", duration_sec)
        
        elif delivery_type == "audio":
            # EMIT a signal to play audio
            # FIX: Use dot notation
            self.app_state["signals"].play_audio.emit(audio_cue)


    def update_reminder_jobs(self):
        """
        (Re)starts all timers based on the current mode.
        """
        scheduler = self.app_state['scheduler']
        scheduler.remove_all_jobs() # Clear old timers

        # Get the settings for the new mode
        modes = config.settings.get("modes", [])
        current_mode = next((m for m in modes if m['id'] == self.app_state['current_mode_id']), None)
        
        if not current_mode:
            print(f"[Engine] Error: Could not find mode {self.app_state['current_mode_id']}")
            return

        print(f"[Engine] Loading timers for mode: {current_mode['name']}")
        
        # Schedule new jobs
        for reminder_id, settings in current_mode.get("reminders", {}).items():
            if settings.get("enabled"):
                interval = settings.get("interval_min", 20)
                
                print(f"  -> Scheduling '{reminder_id}' every {interval} min")
                
                scheduler.add_job(
                    self.trigger_scheduled_reminder,
                    'interval',
                    minutes=interval,
                    id=reminder_id,
                    args=[reminder_id]
                )
        
        # Add the 2-second system check job
        scheduler.add_job(
            self.check_system_state,
            'interval',
            seconds=2,
            id='system_check'
        )

    def pause_reminder_jobs(self):
        """Pauses all reminders, but KEEPS the system_check running."""
        print("[Engine] Pausing reminder jobs (AFK)...")
        for job in self.app_state['scheduler'].get_jobs():
            if job.id != 'system_check':
                job.pause()

    def resume_reminder_jobs(self):
        """Resumes all paused reminders."""
        print("[Engine] Resuming reminder jobs (user back)...")
        for job in self.app_state['scheduler'].get_jobs():
            if job.id != 'system_check':
                job.resume()
                
    def check_system_state(self):
        """
        Runs every 2 seconds to check AFK and active window.
        """
        was_afk = self.app_state['is_afk']
        
        # 1. Check for Work App
        self.app_state['is_work_app_active'] = fn.is_work_app_active()
        
        # 2. Check for AFK
        afk_threshold = config.settings.get("global_settings", {}).get("afk_threshold_sec", 300)
        
        if self.app_state['is_work_app_active']:
            # If on a work app, update last active time
            self.app_state['last_active_time'] = time.time()
            self.app_state['is_afk'] = False
        else:
            # If not on a work app, check if AFK threshold is met
            idle_time = time.time() - self.app_state['last_active_time']
            if idle_time > afk_threshold:
                self.app_state['is_afk'] = True
            
        # --- Handle State Changes ---
        if self.app_state['is_afk'] and not was_afk:
            # User just went AFK
            self.pause_reminder_jobs()
            
        elif not self.app_state['is_afk'] and was_afk:
            # User just came back from AFK
            self.resume_reminder_jobs()

    def set_current_mode(self, mode_id):
        """
        SLOT: Called from the UI to change the active mode.
        """
        if mode_id == self.app_state['current_mode_id']:
            return # No change
            
        print(f"[Engine] Changing mode to {mode_id}")
        self.app_state['current_mode_id'] = mode_id
        
        # Save this change to config
        config.settings['active_mode_id'] = mode_id # Update in memory
        config.save_settings(config.settings)      # Save to file
        
        # Restart all timers with the new mode's schedule
        self.update_reminder_jobs()

    def start_pulsebreak_engine(self):
        """
        Main entry point for the backend thread.
        """
        print("[Engine] PulseBreak Engine Starting...")
        
        # Get default mode from config
        default_mode_id = "mode_001" # Fallback
        modes = config.settings.get("modes", [])
        for mode in modes:
            if mode.get("is_default"):
                default_mode_id = mode.get("id")
                break
        
        # Set the active mode (which also loads the timers)
        self.set_current_mode(
            config.settings.get("active_mode_id", default_mode_id)
        )
        
        # Start the scheduler
        try:
            self.app_state['scheduler'].start()
            print("[Engine] Scheduler started.")
        except Exception as e:
            print(f"[Engine] CRITICAL: Could not start scheduler: {e}")

    def stop_engine(self):
        """Stops the scheduler."""
        print("[Engine] Shutting down scheduler...")
        try:
            self.app_state['scheduler'].shutdown()
        except Exception as e:
            print(f"[Engine] Error during scheduler shutdown: {e}")

