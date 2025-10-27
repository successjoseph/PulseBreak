"""
This file creates the main Settings window for PulseBreak.
It loads and displays all the settings from config.py
NOW DESIGNED AS A POPUP WIDGET.
"""

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame, QPushButton, QStackedWidget,
    QListWidget, QListWidgetItem, QCheckBox, QSpinBox, QComboBox,
    QGridLayout, QLineEdit, QTextEdit, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QColor

# We must import config from the backend
try:
    # This assumes run.py has added 'backend' to the sys.path
    import config # type: ignore[import]
except ImportError:
    # Fallback for testing settings.py directly
    print("Warning: Could not import config. Running in standalone test mode.")
    import os
    # Fallback needs os module
    if 'os' not in locals() and 'os' not in globals():
        import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
    import config # type: ignore[import]


# --- Main Settings Window (as a Popup Widget) ---
class SettingsWindow(QWidget): # Changed from QMainWindow
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PulseBreak Settings")
        self.setMinimumSize(800, 600)

        # --- Popup Window Flags ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |    # No border or title bar
            Qt.WindowType.Tool |                   # Doesn't show in taskbar
            Qt.WindowType.WindowStaysOnTopHint     # Stays on top
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # Allows rounded corners

        # --- Main Frame (Visible Background) ---
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setStyleSheet("""
            #mainFrame {
                background-color: #F9FAFB; /* Light background */
                border-radius: 10px;
                border: 1px solid #E5E7EB; /* Light border */
            }
        """)
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        self.main_frame.setGraphicsEffect(shadow)

        # Use a layout for the main QWidget to hold the frame
        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.main_frame)
        # Margins are handled by the frame's layout now

        # --- Main Layout (inside the frame) ---
        self.main_layout = QHBoxLayout(self.main_frame) # Layout applied to the frame
        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0) # No margins for the main layout

        # --- Close Button ---
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
                color: #6B7280;
            }
            QPushButton:hover {
                color: #111827;
            }
        """)
        self.close_button.clicked.connect(self.close)

        # Layout specifically for the close button
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.close_button)
        top_bar_layout.setContentsMargins(5, 5, 5, 5) # Small margin for close button

        # --- Container for Sidebar + Content ---
        container_widget = QWidget()
        container_layout = QHBoxLayout(container_widget)
        container_layout.setSpacing(0)
        container_layout.setContentsMargins(0, 0, 0, 0)

        # --- 1. Navigation Sidebar ---
        self.nav_widget = QWidget()
        self.nav_widget.setObjectName("sidebar")
        self.nav_widget.setFixedWidth(200)
        # Basic sidebar style
        self.nav_widget.setStyleSheet("#sidebar { background-color: #ffffff; border-right: 1px solid #E5E7EB; border-top-left-radius: 10px; border-bottom-left-radius: 10px; }") # Added radius
        self.nav_layout = QVBoxLayout(self.nav_widget)
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_layout.setContentsMargins(0, 10, 0, 10) # Padding top/bottom

        self.nav_list = QListWidget()
        self.nav_list.addItem("General")
        self.nav_list.addItem("Modes")
        self.nav_list.addItem("Work Apps")
        self.nav_list.addItem("Affirmations")
        self.nav_list.addItem("About")
        # Basic list style
        self.nav_list.setStyleSheet("""
            QListWidget { border: none; }
            QListWidget::item { padding: 10px 15px; }
            QListWidget::item:selected {
                background-color: #EFF6FF;
                color: #1D4ED8;
                font-weight: bold;
                border-left: 3px solid #3B82F6;
             }
        """)
        self.nav_layout.addWidget(self.nav_list)

        # --- 2. Content Area (Stacked Widget) ---
        self.content_stack = QStackedWidget()
        # Add padding to content area
        self.content_stack.setStyleSheet("QStackedWidget { padding: 10px; }")

        self.page_general = self.create_general_page()
        self.page_modes = self.create_modes_page()
        self.page_apps = self.create_work_apps_page()
        self.page_affirmations = self.create_affirmations_page()
        self.page_about = self.create_about_page()

        self.content_stack.addWidget(self.page_general)
        self.content_stack.addWidget(self.page_modes)
        self.content_stack.addWidget(self.page_apps)
        self.content_stack.addWidget(self.page_affirmations)
        self.content_stack.addWidget(self.page_about)

        # --- Add sidebar and content to container ---
        container_layout.addWidget(self.nav_widget)
        container_layout.addWidget(self.content_stack)

        # --- Add top bar and container to main layout ---
        main_content_layout = QVBoxLayout() # Vertical layout for top bar + rest
        main_content_layout.addLayout(top_bar_layout)
        main_content_layout.addWidget(container_widget)
        self.main_layout.addLayout(main_content_layout) # Add this to the frame's layout

        # --- Connect Signals ---
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0) # Start on "General"

    def create_page_container(self, title):
        """Helper to create a standard page layout (simplified styling)"""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px;")
        page_layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }") # Match background

        scroll_content = QWidget()
        scroll.setWidget(scroll_content)

        content_layout = QVBoxLayout(scroll_content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setSpacing(10)

        page_layout.addWidget(scroll)

        return page, content_layout

    # --- 1. General Page ---
    def create_general_page(self):
        page, layout = self.create_page_container("General Settings")

        g_settings = config.settings.get("global_settings", {})

        layout.addWidget(self.create_setting_row(
            "Run on Startup",
            "Automatically start PulseBreak when your computer turns on.",
            QCheckBox(),
            g_settings.get("run_on_startup", False)
        ))

        theme_combo = QComboBox()
        theme_combo.addItems(["system", "light", "dark"])
        layout.addWidget(self.create_setting_row(
            "Theme",
            "Choose the app's color theme.",
            theme_combo,
            g_settings.get("theme", "system")
        ))

        afk_spin = QSpinBox()
        afk_spin.setRange(30, 3600)
        afk_spin.setSuffix(" seconds")
        afk_value = int(g_settings.get("afk_threshold_sec", 300))
        layout.addWidget(self.create_setting_row(
            "AFK Threshold",
            "Time of inactivity before pausing reminders.",
            afk_spin,
            afk_value
        ))

        layout.addStretch()
        return page

    # --- 2. Modes Page ---
    def create_modes_page(self):
        page, layout = self.create_page_container("Manage Modes")

        modes = config.settings.get("modes", [])

        for mode in modes:
            mode_widget = QFrame() # Use QFrame for border
            mode_widget.setObjectName("card")
            mode_widget.setFrameShape(QFrame.Shape.StyledPanel) # Add default panel look
            mode_widget.setStyleSheet("#card { border: 1px solid #E5E7EB; border-radius: 5px; padding: 10px; margin-bottom: 10px; }")
            mode_layout = QGridLayout(mode_widget)

            mode_name_label = QLabel(mode.get("name", "Unnamed Mode"))
            mode_name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            mode_layout.addWidget(mode_name_label, 0, 0, 1, 5)

            # Reminder Headers
            mode_layout.addWidget(QLabel("Reminder"), 1, 0)
            mode_layout.addWidget(QLabel("Enabled"), 1, 1)
            mode_layout.addWidget(QLabel("Interval (min)"), 1, 2)
            mode_layout.addWidget(QLabel("Delivery"), 1, 3)
            mode_layout.addWidget(QLabel("Duration (sec)"), 1, 4)

            row = 2
            for r_id, r_settings in mode.get("reminders", {}).items():
                r_name = config.settings.get("reminder_library", {}).get(r_id, {}).get("name", r_id)

                toggle = QCheckBox()
                interval_spin = QSpinBox()
                interval_spin.setRange(1, 240)
                delivery_combo = QComboBox()
                delivery_combo.addItems(["popup", "audio"])
                duration_spin = QSpinBox()
                duration_spin.setRange(0, 300)
                duration_spin.setSuffix(" sec")

                mode_layout.addWidget(QLabel(r_name), row, 0)
                mode_layout.addWidget(toggle, row, 1, Qt.AlignmentFlag.AlignCenter)
                mode_layout.addWidget(interval_spin, row, 2)
                mode_layout.addWidget(delivery_combo, row, 3)
                mode_layout.addWidget(duration_spin, row, 4)

                toggle.setChecked(r_settings.get("enabled", False))
                interval_spin.setValue(int(r_settings.get("interval_min", 20)))
                delivery_combo.setCurrentText(r_settings.get("delivery", "popup"))
                duration_spin.setValue(int(r_settings.get("duration_sec", 10)))

                row += 1

            layout.addWidget(mode_widget)

        layout.addStretch()
        return page

    # --- 3. Work Apps Page ---
    def create_work_apps_page(self):
        page, layout = self.create_page_container("Work Applications")

        layout.addWidget(QLabel("This list is auto-synced from your `labeller.json` file."))

        app_list_widget = QListWidget()
        work_apps = config.settings.get("work_apps", [])
        if work_apps:
            app_list_widget.addItems(work_apps)
        else:
            app_list_widget.addItem("No work apps labeled yet. Run labeller.py!")

        layout.addWidget(app_list_widget)

        layout.addStretch()
        return page

    # --- 4. Affirmations Page ---
    def create_affirmations_page(self):
        page, layout = self.create_page_container("Affirmation Library")

        affirmations = config.settings.get("affirmation_library", [])

        text_edit = QTextEdit()
        text_edit.setPlainText("\n".join(affirmations))
        text_edit.setPlaceholderText("Enter one affirmation per line...")

        layout.addWidget(QLabel("Edit your list of affirmations below (one per line)."))
        layout.addWidget(text_edit)

        layout.addStretch()
        return page

    # --- 5. About Page ---
    def create_about_page(self):
        page, layout = self.create_page_container("About PulseBreak")

        version = config.settings.get("version", "0.0.0")
        layout.addWidget(QLabel(f"PulseBreak v{version}"))
        layout.addWidget(QLabel("A smart break and affirmation system."))

        sys_info = config.settings.get("system_info", {})
        info_text = (
            "System Info:\n"
            f"- OS: {sys_info.get('os')} {sys_info.get('os_release')}\n"
            f"- Platform: {sys_info.get('platform')}\n"
            f"- Python: {sys_info.get('python_version')}\n"
            f"- User: {sys_info.get('username')}"
        )
        layout.addWidget(QLabel(info_text))

        layout.addStretch()
        return page

    def create_setting_row(self, name, description, widget, current_value=None):
        """Helper to create a consistent settings row"""
        row_widget = QWidget()
        row_widget.setObjectName("settingRow")
        # Simplified row style
        row_widget.setStyleSheet("#settingRow { border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 10px; }")
        row_layout = QHBoxLayout(row_widget)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)

        name_label = QLabel(name)
        # Simplified name style
        # name_label.setStyleSheet("font-weight: bold;")
        desc_label = QLabel(description)
        # Simplified description style
        # desc_label.setStyleSheet("color: #555;")

        left_layout.addWidget(name_label)
        left_layout.addWidget(desc_label)

        row_layout.addWidget(left_widget)
        row_layout.addStretch()

        # Set the widget's current state
        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(current_value))
        elif isinstance(widget, QComboBox):
            widget.setCurrentText(str(current_value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(current_value if current_value is not None else 0))

        row_layout.addWidget(widget)

        return row_widget

    # --- STYLESHEET FUNCTION REMOVED ---

# --- Self-Test ---
if __name__ == "__main__":
    # Fallback needs os module
    if 'os' not in locals() and 'os' not in globals():
        import os

    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())

