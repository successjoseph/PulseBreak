PulseBreak ⏰

A smart break and affirmation system to keep you healthy and focused during long sessions at the computer.

(Add a GIF or screenshot here of the bubble, the tray, and the settings window)

PulseBreak is a lightweight desktop app that monitors your "work applications" (like VS Code, Chrome, etc.) and provides timely reminders based on your current activity mode.

It's designed to be lightweight, themeable, and highly customizable, giving you control over when and how you're reminded.

✨ Core Features

Smart App Detection: Reminders only activate when you're using a designated "work app."

Customizable Modes: Create different modes (e.g., "Intense Focus," "At Work") with their own unique reminder rules.

Queued Reminders: Popups and audio reminders will queue up, so you never miss one, even if they fire at the same time.

Themeable UI: Customize the app's look and feel. Includes 7+ built-in themes like "Obsidian" and "Graphite."

Text-to-Speech: "Audio-only" modes will speak the reminder to you instead of showing a visual popup, keeping you in the flow.

GUI-Based Labeller: Scan for new apps and add them to your "work apps" list directly from the settings menu.

Auto-Save: All settings save instantly—no "Save" button needed.

🧱 Tech Stack

Frontend (UI): Python + PyQt6

Backend (Engine): Python + APScheduler (for timers)

App Detection: Python + psutil

Sound: PyQt6.QtMultimedia

Speech: PyQt6.QtTextToSpeech

Installer: cx_Freeze + Inno Setup

🚀 How to Use (for Development)

Clone the repository: git clone https://github.com/successjoseph/PulseBreak.git

Install dependencies: pip install -r requirements.txt

Run the app: python run.py

📂 How to Build the Installer

This project uses cx_Freeze to build the app folder and Inno Setup to create the final setup.exe.

Build with cx_Freeze:

python setup.py build


This creates a build/PulseBreak folder containing PulseBreak.exe and all its files.

Compile with Inno Setup:

Download and install Inno Setup.

Open setup_script.iss in the Inno Setup Compiler.

Click Build -> Compile.

Your final PulseBreak_Setup.exe will be in the Output folder.

⬆️ Updates

You can check for new versions by going to the Update tab in the app's settings, or by visiting the Releases page for this repo.