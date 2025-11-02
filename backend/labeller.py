import psutil
import json
import os
import sys

# --- MODIFIED: Use config for paths ---
# We now import config to get the correct absolute paths
try:
    from . import config
except ImportError:
    # This allows the script to still be run standalone for testing
    import config

# Define the output file path from the config
LABELS_FILE = config.LABELS_FILE
# --- END MODIFICATION ---

def load_existing_labels():
    """
    Loads the set of apps already in labeller.json.
    """
    try:
        with open(LABELS_FILE, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def get_unique_processes():
    """
    Gets a set of unique, running process names,
    FILTERING OUT system processes from the C:Windows directory.
    
    Returns: set of process names (e.g., {"chrome.exe", "Code.exe"})
    """
    unique_apps = set()
    print("Scanning all running processes (and filtering out system apps)...")
    
    windows_dir = ""
    if sys.platform == 'win32':
        windows_dir = os.environ.get('WINDIR', 'C:\\Windows').lower()

    for proc in psutil.process_iter(['name', 'exe']):
        try:
            proc_info = proc.info
            proc_name = proc_info['name']
            proc_exe_path = proc_info['exe']

            if not proc_name or not proc_exe_path:
                continue

            if sys.platform == 'win32' and proc_exe_path.lower().startswith(windows_dir):
                continue
            
            unique_apps.add(proc_name)

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass 
        except TypeError:
            pass 

    print(f"Found {len(unique_apps)} unique *non-system* processes.\n")
    return unique_apps

def save_labels(work_apps_set):
    """
    Saves the set of work apps to the JSON file.
    """
    try:
        final_list = sorted(list(work_apps_set))
        
        with open(LABELS_FILE, 'w') as f:
            json.dump(final_list, f, indent=4)
        print(f"\nSUCCESS: Saved {len(final_list)} total work apps to {LABELS_FILE}")
    except Exception as e:
        print(f"\nERROR: Could not save file. {e}")

# --- Kept for standalone testing, but no longer the main use ---
def run_console_labeller():
    """
    Loops through unique processes and asks the user to label them,
    skipping any apps that are already labelled.
    """
    print("--- PulseBreak App Labeller (Update Mode) ---")
    
    existing_work_apps = load_existing_labels()
    if existing_work_apps:
        print(f"Loaded {len(existing_work_apps)} existing work apps from {LABELS_FILE}.")
    
    all_running_apps = get_unique_processes()

    new_apps_to_label = all_running_apps.difference(existing_work_apps)
    
    if not new_apps_to_label:
        print("Looks like your app list is up to date! No new non-system apps found running.")
        return list(existing_work_apps) 

    print("--- Labelling New Apps ---")
    print(f"You have {len(new_apps_to_label)} new apps to label.")
    print(" (y = yes, n = no, s = skip) \n")
    
    updated_work_apps_set = existing_work_apps
    
    for app_name in sorted(list(new_apps_to_label)):
        while True:
            try:
                print(f"Is '{app_name}' a work app? (y/n/s): ", end="", flush=True)
                choice = input().lower().strip()
                
                if choice == 'y':
                    updated_work_apps_set.add(app_name)
                    print(f"  -> ADDED: {app_name}\n")
                    break
                elif choice == 'n' or choice == 's':
                    print(f"  -> SKIPPED: {app_name}\n")
                    break
                else:
                    print("  -> Invalid input. Please enter 'y', 'n', or 's'.")
                    
            except KeyboardInterrupt:
                print("\nLabelling stopped. Saving current progress...")
                return updated_work_apps_set
            except EOFError:
                print("\nEOF detected. Stopping.")
                return updated_work_apps_set

    return updated_work_apps_set

if __name__ == "__main__":
    labelled_apps_set = run_console_labeller()
    if labelled_apps_set:
        save_labels(labelled_apps_set)
    else:
        print("\nNo applications were labelled.")