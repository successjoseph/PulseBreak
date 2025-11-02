PulseBreak

<img width="818" height="600" alt="General settings" src="https://github.com/user-attachments/assets/4f78b3e1-c8e7-44fe-9706-d3e22ad738ec" />
<img width="818" height="600" alt="manage modes" src="https://github.com/user-attachments/assets/758d9846-2582-4984-a066-a31e94589649" />
<img width="818" height="600" alt="manage modes system theme" src="https://github.com/user-attachments/assets/b4af9c42-d434-46ef-9348-12639554a02d" />
<img width="818" height="600" alt="general settings coffee house theme" src="https://github.com/user-attachments/assets/13409ab6-d410-4f1b-ac81-bdd331bad165" />


A smart wellness and productivity companion for your desktop.

PulseBreak is a lightweight, themeable app that monitors your "work applications" (like your code editor or browser) and provides context-aware reminders. It's designed to help you build healthy habits, stay focused, and maintain a positive mindset during long sessions at the computer.

It uses an "Away From Work" (AFW) logic, pausing all reminders the moment you switch to a non-work app and seamlessly resuming when you're back.

✨ Core Features

Floating Bubble UI: A minimal, draggable bubble gives you quick access to all your modes.

Smart "Away From Work" (AFW) Detection: Reminders intelligently pause when you're not using your designated "work apps" and resume instantly when you're back.

Customizable Modes: Create different profiles for your work. The default "Intense Focus" mode uses subtle audio-only alerts, while "At Work" uses full-screen popups.

Full Theme Engine: Customize the app's entire look and feel. Comes with 7+ themes (like Obsidian, Graphite, and Zen Garden) and you can edit them via themes.json.

Popup & Audio Reminders: Get 80% screen-covering popups (with a timer bar) that queue up so you never miss one, or get subtle Text-to-Speech (TTS) reminders that speak to you.

GUI App Labeller: No more editing JSON files. The "Work Apps" page in Settings lets you scan your running applications and add/remove new "work apps" with a single click.

Add/Delete Modes: You can now create, customize, and delete modes directly from the settings panel.

Auto-Save: All settings (general, modes, affirmations) save automatically the moment you change them.

Update Checker: The "Update" page links directly to the project's GitHub Releases page.

⚙️ How to Install (from Release)

Go to the Releases Page.

Download the PulseBreak_Setup.exe from the latest release.

Run the installer. It will automatically install to your AppData folder and create shortcuts.

🛠️ Tech Stack

Frontend (GUI): Python + PyQt6

Backend (Logic): Python

Scheduling: apscheduler

App Detection: psutil

Sound/TTS: PyQt6.QtMultimedia, PyQt6.QtTextToSpeech

Installer: PyInstaller


