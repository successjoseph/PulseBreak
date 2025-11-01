"""
This file creates the floating bubble UI AND the settings popup.
It is now designed to be imported and run by run.py.
It emits signals to the backend and receives data to populate itself.
"""

import sys
import uuid # For generating unique mode IDs
import os # For sound file paths
import json # <-- FIX: Added missing json import
from functools import partial # For connecting signals with arguments

from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QFrame, QHBoxLayout,
    QGraphicsDropShadowEffect, QStackedWidget, QScrollArea,
    QCheckBox, QSpinBox, QComboBox, QGridLayout, QTextEdit,
    QInputDialog, QMessageBox
)
from PyQt6.QtCore import (Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve,
                          QRect, QSize, pyqtSignal, QObject, QRectF, QUrl) # Added QUrl
# Import QPaintEvent for type hinting
from PyQt6.QtGui import QColor, QPalette, QIcon, QPainter, QPen, QMouseEvent, QGuiApplication, QPaintEvent
# Import new modules for sound and TTS
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtTextToSpeech import QTextToSpeech

# We must import config from the backend
try:
    # This assumes run.py has added 'backend' to the sys.path
    import config # type: ignore[import]
except ImportError:
    # Fallback for testing
    print("Warning: Could not import config. Running in standalone test mode.")
    import os
    # Fallback needs os module
    if 'os' not in locals() and 'os' not in globals():
        import os
    sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
    import config # type: ignore[import]


# --- +++ Theme Manager +++ ---
# This helper class will load and manage all theme data
class ThemeManager:
    def __init__(self):
        self.themes = []
        self.load_themes()

    def load_themes(self):
        try:
            with open(config.THEMES_FILE, 'r') as f:
                theme_data = json.load(f) # <-- FIX: Pylance error, json was undefined
                self.themes = theme_data.get("themes", [])
                print(f"[ThemeManager] Loaded {len(self.themes)} themes.")
        except Exception as e:
            print(f"[ThemeManager] CRITICAL: Could not load themes.json: {e}")
            self.themes = [] # Use empty list as fallback

    def get_theme_by_id(self, theme_id):
        """Finds a theme in the list by its ID."""
        for theme in self.themes:
            if theme.get("id") == theme_id:
                return theme
        return None # Not found

    def get_active_theme_colors(self):
        """Gets the colors for the currently active theme in config."""
        active_id = config.settings.get("global_settings", {}).get("active_theme_id", "theme_obsidian_01")
        
        # Special case: System theme
        if active_id == "system":
            # TODO: Implement light/dark detection
            # For now, return a basic light theme
            print("[ThemeManager] 'System' theme active (using fallback light).")
            return {
                "background": "#F9FAFB", "surface": "#FFFFFF", "primary": "#3B82F6",
                "secondary": "#9CA3AF", "text_primary": "#1F2937", "text_secondary": "#4B5563",
                "text_accent": "#3B82F6", "border": "#E5E7EB", "hover_bg": "#F3F4F6",
                "selected_bg": "#EFF6FF", "selected_text": "#3B82F6", "success": "#22C55E"
            }

        theme = self.get_theme_by_id(active_id)
        if theme:
            print(f"[ThemeManager] Applying theme: {theme.get('name')}")
            return theme.get("colors", {})
        
        # Fallback if theme_id is invalid
        print(f"[ThemeManager] Warning: Active theme '{active_id}' not found. Falling back to Obsidian.")
        theme = self.get_theme_by_id("theme_obsidian_01")
        if theme:
            return theme.get("colors", {})
        
        # Absolute fallback
        return {"background": "#FFFFFF", "primary": "#000000"} # Basic fallback


# --- Icons ---
ICON_CLOCK = "⏰" # Using emoji again, ensure your system supports it
ICON_SETTINGS = "⚙️"
ICON_QUIT = "➡️"
ICON_DELETE = "🗑️" # Trashcan icon


# --- Custom Draggable Bubble ---
class DraggableBubble(QPushButton):
    """
    A custom QPushButton that is draggable and also detects clicks.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.parent_window = parent

        # Drag state
        self.drag_start_pos: QPoint | None = None
        self.window_start_pos: QPoint | None = None
        self.is_dragging = False

    def mousePressEvent(self, event: QMouseEvent): # type: ignore[override]
        """Store the start position of a potential drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            # Find the parent QWidget (our main window) to move it
            window = self.window()
            if window:
                self.window_start_pos = window.frameGeometry().topLeft()
            self.is_dragging = False # Haven't moved yet
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent): # type: ignore[override]
        """If the mouse moves significantly, start dragging the window."""
        if (event.buttons() == Qt.MouseButton.LeftButton and
            self.drag_start_pos is not None and
            self.window_start_pos is not None):

            delta = event.globalPosition().toPoint() - self.drag_start_pos

            # Start dragging only if moved more than a few pixels
            if delta.manhattanLength() > 3: # Use QApplication.startDragDistance() ideally
                self.is_dragging = True

            if self.is_dragging:
                window = self.window()
                if window:
                    # Make sure window_start_pos is valid before adding delta
                    current_pos = self.window_start_pos
                    if current_pos is not None:
                        window.move(current_pos + delta)

            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent): # type: ignore[override]
        """
        If this was a "click" (not a drag), emit the clicked signal.
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_dragging:
                # This was a click, not a drag.
                self.clicked.emit()

            # Reset drag state
            self.drag_start_pos = None
            self.window_start_pos = None
            self.is_dragging = False
            event.accept()


# --- 80% Dark Reminder Popup Widget ---
class PopupWidget(QWidget):
    """
    The 80% screen popup widget for reminders.
    """
    closed = pyqtSignal() # Signal to tell the BubbleWidget we are done

    def __init__(self, title, message, duration_sec, colors): # Pass in theme colors
        super().__init__()

        self.title_text = title
        self.message_text = message
        self.duration_ms = max(100, duration_sec * 1000) # Ensure duration is at least 100ms
        self.elapsed_ms = 0
        self.colors = colors # Store theme colors

        # --- Window Setup ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool # Prevents it from showing in taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # --- Sizing (80% of screen) ---
        primary_screen = QGuiApplication.primaryScreen()
        if not primary_screen:
            print("[UI Error] Cannot get primary screen info for popup.")
            # Don't try to show if we can't get screen info
            # A timer will close this invisible widget after duration
            QTimer.singleShot(self.duration_ms, self.close_popup)
            return

        screen_geo = primary_screen.availableGeometry() # Use availableGeometry

        # Use _popup_width to avoid name clash
        self._popup_width = int(screen_geo.width() * 0.8)
        self._popup_height = int(screen_geo.height() * 0.8)
        self.resize(self._popup_width, self._popup_height)

        # Center it
        self.move(
            screen_geo.left() + int((screen_geo.width() - self._popup_width) / 2),
            screen_geo.top() + int((screen_geo.height() - self._popup_height) / 2)
        )

        # --- Timer for the orange bar and auto-close ---
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer)
        # Use a slightly longer interval for potentially better performance
        self.timer_interval = 100 # ms
        self.timer.start(self.timer_interval)

    def update_timer(self):
        """Called by timer to update the timer bar."""
        self.elapsed_ms += self.timer_interval
        if self.elapsed_ms >= self.duration_ms:
            self.timer.stop()
            self.close_popup()
        else:
            self.update() # Trigger a repaint

    def paintEvent(self, event: QPaintEvent): # type: ignore[override]
        """Custom paint event to draw the dark background and timer."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Background (from theme)
        # Use .get() with fallback colors
        bg_hex = self.colors.get("background", "#1F2937")
        bg_color = QColor(bg_hex)
        bg_color.setAlpha(int(255 * 0.95)) # 95% opacity
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(self.rect()), 16.0, 16.0)

        # --- Calculate vertical positions dynamically ---
        content_margin = 40
        available_height = self._popup_height - (2 * content_margin) - 10 # Reserve 10 for timer bar
        title_height_estimate = 50
        message_max_height = available_height - title_height_estimate - 20 # 20px spacing

        # 2. Text (Title)
        painter.setPen(QColor(self.colors.get("text_primary", "#FFFFFF")))
        font = painter.font()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)

        # Center title vertically somewhat
        title_y_pos = content_margin + int(available_height * 0.2)
        title_rect = QRect(content_margin, title_y_pos, self._popup_width - (2*content_margin), title_height_estimate)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.title_text)

        # 3. Text (Message)
        font.setPointSize(16)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(self.colors.get("text_secondary", "#E5E7EB")))

        # Center message below title
        msg_y_pos = title_y_pos + title_height_estimate + 20
        msg_rect = QRect(content_margin, msg_y_pos, self._popup_width - (2*content_margin), message_max_height)

        # Use Qt.TextFlag.TextWordWrap for word wrapping
        painter.drawText(QRectF(msg_rect),
                         int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), # Combine flags as int
                         self.message_text)

        # 4. Timer Bar (from theme)
        if self.duration_ms > 0:
            progress = self.elapsed_ms / self.duration_ms
            bar_width = self._popup_width * (1.0 - progress) # Bar shrinks from right to left

            painter.setBrush(QColor(self.colors.get("primary", "#F97316")))
            # Draw from bottom-left, full width initially, shrinking
            painter.drawRect(0, self._popup_height - 10, int(bar_width), 10)

    def close_popup(self):
        self.closed.emit()
        self.close()


# --- MERGED Settings Popup Widget ---
class SettingsPopup(QWidget):
    # Signal to tell BubbleWidget to refresh its mode list and theme
    settings_changed_signal = pyqtSignal()

    def __init__(self, theme_manager, parent=None): # Accept theme manager
        super().__init__(parent) # Pass parent
        
        self.theme_manager = theme_manager
        self.colors = self.theme_manager.get_active_theme_colors() # Get current colors
        
        self.setWindowTitle("PulseBreak Settings")
        self.setMinimumSize(800, 600)

        # --- Popup Window Flags ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # --- Main Frame (Visible Background) ---
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("mainFrame")
        
        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15); shadow.setColor(QColor(0, 0, 0, 60)); shadow.setOffset(0, 4)
        self.main_frame.setGraphicsEffect(shadow)

        outer_layout = QVBoxLayout(self); outer_layout.addWidget(self.main_frame)
        outer_layout.setContentsMargins(10, 10, 10, 10)

        self.main_layout = QHBoxLayout(self.main_frame); self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Close Button ---
        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(24, 24)
        self.close_button.clicked.connect(self.close)

        top_bar_layout = QHBoxLayout(); top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.close_button)
        top_bar_layout.setContentsMargins(0, 5, 5, 0)

        # --- Container for Sidebar + Content ---
        container_widget = QWidget(); container_layout = QHBoxLayout(container_widget)
        container_layout.setSpacing(0); container_layout.setContentsMargins(0, 0, 0, 0)

        # --- 1. Navigation Sidebar ---
        self.nav_widget = QWidget(); self.nav_widget.setObjectName("sidebar")
        self.nav_widget.setFixedWidth(200)
        self.nav_layout = QVBoxLayout(self.nav_widget)
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_layout.setContentsMargins(0, 10, 0, 10)

        self.nav_list = QListWidget()
        self.nav_list.addItem("General")
        self.nav_list.addItem("Modes")
        self.nav_list.addItem("Work Apps")
        self.nav_list.addItem("Affirmations")
        self.nav_list.addItem("Update") # <-- NEW
        self.nav_list.addItem("About")
        self.nav_layout.addWidget(self.nav_list)

        # --- 2. Content Area (Stacked Widget) ---
        self.content_stack = QStackedWidget()
        
        # Create pages using helper methods
        self.page_general = self._create_general_page()
        self.page_modes, self.modes_layout_container = self._create_modes_page_structure()
        self.page_apps = self._create_work_apps_page()
        self.page_affirmations = self._create_affirmations_page()
        self.page_update = self._create_update_page() # <-- NEW
        self.page_about = self._create_about_page()

        # Add pages to stack
        self.content_stack.addWidget(self.page_general)
        self.content_stack.addWidget(self.page_modes)
        self.content_stack.addWidget(self.page_apps)
        self.content_stack.addWidget(self.page_affirmations)
        self.content_stack.addWidget(self.page_update) # <-- NEW
        self.content_stack.addWidget(self.page_about)

        # Populate the initial modes page content
        self._build_mode_cards()

        # --- Assemble Layout ---
        container_layout.addWidget(self.nav_widget)
        container_layout.addWidget(self.content_stack)
        main_content_layout = QVBoxLayout()
        main_content_layout.addLayout(top_bar_layout)
        main_content_layout.addWidget(container_widget)
        self.main_layout.addLayout(main_content_layout)

        # --- Connect Signals ---
        self.nav_list.currentRowChanged.connect(self.content_stack.setCurrentIndex)
        self.nav_list.setCurrentRow(0) # Start on "General"
        
        self.apply_theme() # Apply theme colors
        self.center_window()

    def center_window(self):
        """Centers the widget on the primary screen."""
        primary_screen = QGuiApplication.primaryScreen()
        if primary_screen:
            screen_geo = primary_screen.availableGeometry()
            center_x = screen_geo.left() + (screen_geo.width() / 2)
            center_y = screen_geo.top() + (screen_geo.height() / 2)
            self.move(
                int(center_x - self.width() / 2),
                int(center_y - self.height() / 2)
            )

    def _create_page_container(self, title):
        """Helper to create a standard page layout (simplified styling)"""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        page_layout.setContentsMargins(10, 10, 10, 10)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle") # Use object name for styling
        page_layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }") # Match background

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background-color: transparent;")
        scroll.setWidget(scroll_content)

        # This layout will hold the actual content (rows, cards, etc.)
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setSpacing(10)

        page_layout.addWidget(scroll)

        # Return the page AND the layout where content should be added
        return page, content_layout

    # --- Page Creation Functions (Minimal Styling) ---
    def _create_general_page(self):
        page, layout = self._create_page_container("General Settings")
        g_settings = config.settings.get("global_settings", {})
        
        # Run on Startup
        layout.addWidget(self._create_setting_row(
            "Run on Startup", "Auto start when computer turns on.",
            QCheckBox(), g_settings.get("run_on_startup", False)))
            
        # Theme Selector
        theme_combo = QComboBox()
        theme_combo.setObjectName("theme_widget") # Special object name
        theme_combo.addItems(["System"] + [t['name'] for t in self.theme_manager.themes])
        
        # Find the name of the active theme
        active_id = g_settings.get("active_theme_id", "system")
        active_theme = self.theme_manager.get_theme_by_id(active_id)
        active_name = "System"
        if active_theme:
            active_name = active_theme.get("name", "System")
        theme_combo.setCurrentText(active_name)
        
        theme_combo.currentTextChanged.connect(self.save_theme_setting) # Special save function
        layout.addWidget(self._create_setting_row(
            "Theme", "Choose the app's color theme.",
            theme_combo, None)) # Value set manually
            
        # AFK Threshold
        afk_spin = QSpinBox(); afk_spin.setRange(30, 3600); afk_spin.setSuffix(" seconds")
        afk_value = int(g_settings.get("afk_threshold_sec", 300))
        layout.addWidget(self._create_setting_row(
            "AFK Threshold", "Time of inactivity before pausing.",
            afk_spin, afk_value))
            
        layout.addStretch()
        return page

    def _create_modes_page_structure(self):
        """Creates the static structure of the modes page (title, scroll, add button)."""
        page, content_layout = self._create_page_container("Manage Modes")

        # Add "Add New Mode" button
        self.add_mode_button = QPushButton(" + Add New Mode") # Store ref
        self.add_mode_button.setObjectName("add_mode_button") # Set object name for styling
        self.add_mode_button.clicked.connect(self.add_new_mode)
        content_layout.insertWidget(0, self.add_mode_button) # Insert at the top

        # Keep a reference to the layout where mode cards will go
        self.modes_layout_container = content_layout
        return page, content_layout # Return both page and layout ref

    def _build_mode_cards(self):
        """Builds and adds the mode card widgets to the modes page layout."""
        # Clear existing mode widgets first (excluding the Add button and stretch)
        for i in reversed(range(self.modes_layout_container.count())):
            item = self.modes_layout_container.itemAt(i)
            # FIX: Check item and item.widget()
            if item:
                widget = item.widget() # Get the widget from the item
                if widget and not isinstance(widget, QPushButton):
                    widget.deleteLater()
                elif item.spacerItem():
                    pass
        
        modes = config.settings.get("modes", [])
        self.mode_widgets = {} 

        for index, mode in enumerate(modes):
            mode_id = mode.get("id")
            if not mode_id: continue 

            mode_widget = QFrame()
            mode_widget.setObjectName(f"card_{mode_id}")
            mode_widget.setFrameShape(QFrame.Shape.StyledPanel)
            mode_layout = QGridLayout(mode_widget)

            # --- Mode Name and Delete Button ---
            name_layout = QHBoxLayout()
            mode_name_label = QLabel(mode.get("name", "Unnamed Mode"))
            mode_name_label.setObjectName("modeCardTitle")
            name_layout.addWidget(mode_name_label)
            name_layout.addStretch()

            delete_button = QPushButton(ICON_DELETE)
            delete_button.setFixedSize(24, 24)
            delete_button.setObjectName("deleteButton")
            delete_button.clicked.connect(partial(self.delete_mode, mode_id))
            name_layout.addWidget(delete_button)

            mode_layout.addLayout(name_layout, 0, 0, 1, 5) # Span 5 columns

            # Reminder Headers (as QLabels)
            headers = ["Reminder", "Enabled", "Interval (min)", "Delivery", "Duration (sec)"]
            for col, text in enumerate(headers):
                header_label = QLabel(text)
                header_label.setObjectName("modeCardHeader")
                mode_layout.addWidget(header_label, 1, col)

            row = 2
            reminder_keys = config.DEFAULT_SETTINGS['reminder_library'].keys()
            mode_reminders = mode.get("reminders", {})

            for r_id in reminder_keys:
                if r_id in mode_reminders:
                    r_settings = mode_reminders[r_id]
                    r_name = config.settings.get("reminder_library", {}).get(r_id, {}).get("name", r_id)

                    toggle = QCheckBox(); interval_spin = QSpinBox(); interval_spin.setRange(1, 240)
                    delivery_combo = QComboBox(); delivery_combo.addItems(["popup", "audio"])
                    duration_spin = QSpinBox(); duration_spin.setRange(0, 300); duration_spin.setSuffix(" sec")
                    
                    # --- FIX: CONNECT WIDGETS TO SAVE FUNCTION ---
                    self.connect_mode_widgets(mode_id, toggle, interval_spin, delivery_combo, duration_spin, r_id)

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

            stretch_index = self.modes_layout_container.count() - 1
            self.modes_layout_container.insertWidget(stretch_index, mode_widget)
            self.mode_widgets[mode_id] = mode_widget 


    def _create_work_apps_page(self):
        page, layout = self._create_page_container("Work Applications")
        layout.addWidget(QLabel("Auto-synced from `labeller.json`."))
        app_list_widget = QListWidget()
        work_apps = config.settings.get("work_apps", [])
        if work_apps: app_list_widget.addItems(work_apps)
        else: app_list_widget.addItem("No work apps labeled. Run labeller.py!")
        layout.addWidget(app_list_widget)
        layout.addStretch()
        return page

    def _create_affirmations_page(self):
        page, layout = self._create_page_container("Affirmation Library")
        affirmations = config.settings.get("affirmation_library", [])
        self.affirmations_text_edit = QTextEdit() # Store reference
        self.affirmations_text_edit.setPlainText("\n".join(affirmations))
        self.affirmations_text_edit.setPlaceholderText("Enter one affirmation per line...")
        layout.addWidget(QLabel("Edit affirmations below (one per line)."))
        layout.addWidget(self.affirmations_text_edit)
        
        save_button = QPushButton("Save Affirmations")
        save_button.setObjectName("saveButton")
        save_button.clicked.connect(self.save_affirmations)
        layout.addWidget(save_button, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()
        return page

    # --- NEW: Update Page ---
    def _create_update_page(self):
        page, layout = self._create_page_container("Check for Updates")
        
        check_button = QPushButton("Check for Updates")
        check_button.setObjectName("saveButton") # Re-use save button style
        check_button.clicked.connect(self.check_for_updates)
        layout.addWidget(check_button, alignment=Qt.AlignmentFlag.AlignLeft)
        
        self.update_status_label = QLabel("Click the button to check for new versions.")
        layout.addWidget(self.update_status_label)

        layout.addStretch()
        return page
        
    def check_for_updates(self):
        # Placeholder function
        self.update_status_label.setText("Checking... (This is a placeholder)")
        # Simulate a check
        QTimer.singleShot(1500, lambda: self.update_status_label.setText("You are running the latest version!"))
    # --- END NEW ---

    def _create_about_page(self):
        page, layout = self._create_page_container("About PulseBreak")
        version = config.settings.get("version", "0.0.0")
        layout.addWidget(QLabel(f"PulseBreak v{version}"))
        layout.addWidget(QLabel("A smart break and affirmation system."))
        sys_info = config.settings.get("system_info", {})
        info_text = ("System Info:\n"
                     f"- OS: {sys_info.get('os')} {sys_info.get('os_release')}\n"
                     f"- Platform: {sys_info.get('platform')}\n"
                     f"- Python: {sys_info.get('python_version')}\n"
                     f"- User: {sys_info.get('username')}")
        layout.addWidget(QLabel(info_text))
        layout.addStretch()
        return page

    def _create_setting_row(self, name, description, widget, current_value=None):
        """Helper to create a consistent settings row (simplified styling)"""
        row_widget = QFrame()
        row_widget.setObjectName("settingRow")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0) # No margins for row layout

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        name_label = QLabel(name)
        name_label.setObjectName("settingName")
        desc_label = QLabel(description)
        desc_label.setObjectName("settingDesc")
        left_layout.addWidget(name_label)
        left_layout.addWidget(desc_label)

        row_layout.addWidget(left_widget)
        row_layout.addStretch()

        # Set the widget's current state and connect signals
        widget_id = f"{name.replace(' ', '_').lower()}_widget" # Create unique ID
        widget.setObjectName(widget_id)

        if isinstance(widget, QCheckBox):
            widget.setChecked(bool(current_value))
            widget.stateChanged.connect(self.save_general_setting) # Connect
        elif isinstance(widget, QComboBox):
            if current_value is not None:
                widget.setCurrentText(str(current_value))
            # Special connection is handled in _create_general_page
            if widget_id != "theme_widget":
                widget.currentTextChanged.connect(self.save_general_setting) # Connect
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(current_value if current_value is not None else 0))
            widget.valueChanged.connect(self.save_general_setting) # Connect

        row_layout.addWidget(widget)

        return row_widget

    # --- Add/Delete/Save Mode Logic ---
    def add_new_mode(self):
        """Handles the 'Add New Mode' button click."""
        mode_name, ok = QInputDialog.getText(self, "New Mode", "Enter name for the new mode:")
        if ok and mode_name:
            print(f"[UI] Adding new mode: {mode_name}")
            new_mode_id = f"mode_{uuid.uuid4().hex[:6]}"
            base_reminders = config.DEFAULT_SETTINGS['modes'][0]['reminders']
            new_reminders = {k: v.copy() for k, v in base_reminders.items()} # Deep copy needed

            new_mode = {
                "id": new_mode_id, "name": mode_name, "is_default": False,
                "reminders": new_reminders
            }
            config.settings['modes'].append(new_mode)
            config.save_settings(config.settings)
            self.refresh_modes_page()
            self.settings_changed_signal.emit() # Notify bubble to refresh

    def delete_mode(self, mode_id_to_delete):
        """Handles the delete button click for a specific mode."""
        print(f"[UI] Request to delete mode: {mode_id_to_delete}")

        modes = config.settings.get("modes", [])
        if len(modes) <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the last mode.")
            return

        mode_to_delete = next((m for m in modes if m.get("id") == mode_id_to_delete), None)
        if not mode_to_delete: return

        if mode_to_delete.get("is_default", False):
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the default mode. Set another as default first.")
            return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Delete '{mode_to_delete.get('name')}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            config.settings['modes'] = [m for m in modes if m.get("id") != mode_id_to_delete]
            active_mode_id = config.settings.get("active_mode_id")
            new_active_mode_id = active_mode_id 

            if active_mode_id == mode_id_to_delete:
                 default_mode = next((m for m in config.settings['modes'] if m.get('is_default')), config.settings['modes'][0])
                 new_active_mode_id = default_mode['id']
                 config.settings['active_mode_id'] = new_active_mode_id
                 print(f"[UI] Deleted active mode, switching to default: {new_active_mode_id}")
                 
                 bubble_parent = self.parent()
                 if isinstance(bubble_parent, BubbleWidget):
                     bubble_parent.mode_changed_signal.emit(new_active_mode_id) # Notify backend

            config.save_settings(config.settings)
            self.refresh_modes_page()
            self.settings_changed_signal.emit() # Notify bubble to refresh

    def refresh_modes_page(self):
        """Clears and rebuilds the mode cards in the UI."""
        print("[UI] Refreshing modes page UI...")
        self._build_mode_cards()

    # --- Save Settings Logic ---
    def save_general_setting(self):
        """Saves changes made on the General Settings page."""
        sender = self.sender()
        if not sender: return

        setting_name_map = {
            "run_on_startup_widget": "run_on_startup",
            "theme_widget": "active_theme_id",
            "afk_threshold_widget": "afk_threshold_sec"
        }
        
        widget_id = sender.objectName()
        if widget_id not in setting_name_map:
            return # Not a widget we're auto-saving
            
        setting_name = setting_name_map[widget_id]
        new_value = None
        needs_backend_update = False 

        if isinstance(sender, QCheckBox):
            new_value = sender.isChecked()
            config.settings['global_settings'][setting_name] = new_value
            # --- FIX: Call set_startup_registry via signal ---
            if setting_name == "run_on_startup":
                bubble_parent = self.parent()
                if isinstance(bubble_parent, BubbleWidget):
                    bubble_parent.startup_setting_changed_signal.emit(new_value)
                    
        elif isinstance(sender, QComboBox):
            # This is handled by save_theme_setting
            return 
        elif isinstance(sender, QSpinBox):
            new_value = sender.value()
            config.settings['global_settings'][setting_name] = new_value
            if setting_name == "afk_threshold_sec":
                needs_backend_update = True 

        if new_value is not None:
            print(f"[UI] Saving General Setting: {setting_name} = {new_value}")
            config.save_settings(config.settings)

            if needs_backend_update:
                bubble_parent = self.parent()
                if isinstance(bubble_parent, BubbleWidget):
                    print("[UI] Notifying backend about AFK threshold change.")
                    current_active_mode = config.settings.get("active_mode_id")
                    if current_active_mode:
                        bubble_parent.mode_changed_signal.emit(current_active_mode)

    def save_theme_setting(self, theme_name):
        """Saves the new theme selection."""
        theme_id = "system"
        if theme_name != "System":
            theme = next((t for t in self.theme_manager.themes if t['name'] == theme_name), None)
            if theme:
                theme_id = theme['id']
        
        print(f"[UI] Saving Theme: {theme_name} (ID: {theme_id})")
        config.settings['global_settings']['active_theme_id'] = theme_id
        config.save_settings(config.settings)
        
        # Apply the new theme
        self.colors = self.theme_manager.get_active_theme_colors()
        self.apply_theme()
        
        # Tell bubble to also apply theme
        self.settings_changed_signal.emit()

    def save_affirmations(self):
        """Saves the affirmations from the text edit."""
        affirmations_text = self.affirmations_text_edit.toPlainText()
        affirmations_list = [line.strip() for line in affirmations_text.splitlines() if line.strip()]
        config.settings['affirmation_library'] = affirmations_list
        config.save_settings(config.settings)
        print(f"[UI] Saved {len(affirmations_list)} affirmations.")
        QMessageBox.information(self, "Saved", "Affirmations updated successfully.")

    def connect_mode_widgets(self, mode_id, toggle, interval_spin, delivery_combo, duration_spin, reminder_id):
        """Connects signals for widgets within a mode card."""
        toggle.stateChanged.connect(lambda state, mid=mode_id, rid=reminder_id: self.save_mode_setting(mid, rid, 'enabled', bool(state)))
        interval_spin.valueChanged.connect(lambda value, mid=mode_id, rid=reminder_id: self.save_mode_setting(mid, rid, 'interval_min', value))
        delivery_combo.currentTextChanged.connect(lambda text, mid=mode_id, rid=reminder_id: self.save_mode_setting(mid, rid, 'delivery', text))
        duration_spin.valueChanged.connect(lambda value, mid=mode_id, rid=reminder_id: self.save_mode_setting(mid, rid, 'duration_sec', value))

    def save_mode_setting(self, mode_id, reminder_id, setting_key, new_value):
        """Saves a specific setting for a reminder within a mode."""
        print(f"[UI] Saving Mode Setting: Mode={mode_id}, Reminder={reminder_id}, Key={setting_key}, Value={new_value}")

        mode = next((m for m in config.settings['modes'] if m.get('id') == mode_id), None)
        if not mode: return

        if reminder_id not in mode['reminders']: return

        # Update the value
        mode['reminders'][reminder_id][setting_key] = new_value
        config.save_settings(config.settings)

        # Check if the currently active mode was changed
        active_mode_id = config.settings.get("active_mode_id")
        if mode_id == active_mode_id:
            print("[UI] Change detected in active mode. Notifying backend.")
            bubble_parent = self.parent()
            if isinstance(bubble_parent, BubbleWidget):
                # Use the existing mode_changed signal to force a reload
                bubble_parent.mode_changed_signal.emit(active_mode_id)
                
    def apply_theme(self):
        """Applies the loaded theme colors to the settings window."""
        c = self.colors
        # FIX: Use single quotes inside f-string for Python < 3.12
        self.main_frame.setStyleSheet(f"""
            #mainFrame {{
                background-color: {c.get('background', '#FFF')};
                border-radius: 10px;
                border: 1px solid {c.get('border', '#E5E7EB')};
            }}
        """)
        self.close_button.setStyleSheet(f"""
            QPushButton {{ background-color: transparent; border: none; font-size: 16px;
                          color: {c.get('text_secondary', '#6B7280')}; padding: 0; margin: 0; }}
            QPushButton:hover {{ color: {c.get('primary', '#F97316')}; }}
        """)
        self.nav_widget.setStyleSheet(f"""
            #sidebar {{ background-color: {c.get('surface', '#FFF')}; 
                      border-right: 1px solid {c.get('border', '#E5E7EB')}; 
                      border-top-left-radius: 10px; border-bottom-left-radius: 10px; }}
        """)
        self.nav_list.setStyleSheet(f"""
            QListWidget {{ border: none; background-color: transparent; color: {c.get('text_secondary', '#374151')}; }}
            QListWidget::item {{ padding: 10px 15px; }}
            QListWidget::item:selected {{ 
                background-color: {c.get('selected_bg', '#EFF6FF')}; 
                color: {c.get('selected_text', '#1D4ED8')}; 
                font-weight: bold; border-left: 3px solid {c.get('primary', '#3B82F6')}; 
            }}
        """)
        # Apply to all children widgets
        # FIX: Use single quotes inside f-strings
        self.setStyleSheet(f"""
            QWidget {{ color: {c.get('text_secondary', '#4B5563')}; }}
            QLabel#pageTitle {{ font-size: 18px; font-weight: bold; margin-bottom: 15px; 
                                padding-left: 5px; color: {c.get('text_primary', '#000')}; }}
            QFrame#settingRow {{ border-bottom: 1px solid {c.get('border', '#eee')}; 
                                 padding-bottom: 10px; margin-bottom: 10px; }}
            QLabel#settingName {{ font-weight: bold; color: {c.get('text_primary', '#000')}; }}
            QLabel#settingDesc {{ color: {c.get('text_secondary', '#555')}; }}
            
            QFrame#card {{ background-color: {c.get('surface', '#FFF')}; border: 1px solid {c.get('border', '#E5E7EB')};
                           border-radius: 5px; padding: 10px; margin-bottom: 10px; }}
            #card QLabel {{ color: {c.get('text_secondary', '#4B5563')}; }}
            #card QLabel#modeCardTitle {{ font-size: 14px; font-weight: bold; color: {c.get('text_primary', '#000')}; }}
            #card QLabel#modeCardHeader {{ color: {c.get('text_secondary', '#6B7280')}; font-size: 11px; font-weight: bold; }}

            QCheckBox, QSpinBox, QComboBox, QLineEdit, QTextEdit {{
                color: {c.get('text_primary', '#000')};
                background-color: {c.get('background', '#FFF')};
                border: 1px solid {c.get('border', '#D1D5DB')};
                border-radius: 4px; padding: 4px;
            }}
            QTextEdit {{ color: {c.get('text_primary', '#000')}; }}
            QPushButton {{
                background-color: {c.get('primary', '#3B82F6')}; color: {c.get('selected_text', '#FFF')}; 
                border: none; padding: 8px 12px; border-radius: 6px; font-weight: 600;
            }}
            QPushButton:hover {{ background-color: {c.get('hover_bg', '#2563EB')}; }}
            
            /* Specific style for Add Mode button */
            QPushButton[objectName="add_mode_button"] {{
                background-color: {c.get('selected_bg', '#E0E7FF')}; color: {c.get('selected_text', '#3730A3')};
                text-align: left;
            }}
            QPushButton[objectName="add_mode_button"]:hover {{
                background-color: {c.get('hover_bg', '#C7D2FE')};
            }}
            /* Specific style for Delete button */
            QPushButton[objectName="deleteButton"] {{
                color: #EF4444; background: transparent; font-size: 16px; padding: 0;
            }}
            QPushButton[objectName="deleteButton"]:hover {{ color: #DC2626; background: transparent; }}
        """)


# --- Main Bubble Widget ---
class BubbleWidget(QWidget):
    # --- Signals from Frontend to Backend ---
    mode_changed_signal = pyqtSignal(str)
    quit_signal = pyqtSignal()
    # --- NEW: Signal for startup setting ---
    startup_setting_changed_signal = pyqtSignal(bool)

    def __init__(self, app_instance=None):
        super().__init__()

# ... inside BubbleWidget.__init__ ...
        self.player.setAudioOutput(self._audio_output)
        self.tts = QTextToSpeech()
        
        # --- NEW: TTS Queue ---
        self.tts_queue = []
        self.is_speaking = False
        # Connect the signal to know when speaking is done
        self.tts.stateChanged.connect(self.on_tts_finished)
        # --- END NEW ---

        # --- Window Setup ---

        self.app = app_instance
        self.settings_popup: SettingsPopup | None = None 
        
        # --- NEW: Init Theme Manager ---
        self.theme_manager = ThemeManager()
        self.colors = self.theme_manager.get_active_theme_colors()

        # --- NEW: Sound and TTS Engines ---
        self.player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self.player.setAudioOutput(self._audio_output)
        self.tts = QTextToSpeech()

        # --- Window Setup ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(256, 300) 

        # --- Position window ---
        try:
            primary_screen = QGuiApplication.primaryScreen()
            if primary_screen:
                screen_geometry = primary_screen.availableGeometry()
                top_right_pos = QPoint(
                    screen_geometry.width() - self.width() - 50,
                    50
                )
                self.move(top_right_pos)
            else: self.move(100, 100) # Fallback
        except Exception as e:
            print(f"[UI] Error setting window position: {e}")
            self.move(100, 100) # Fallback

        # --- State ---
        self.is_tray_open = False
        self.modes_map = {} 
        self.popup_queue = [] 
        self.is_popup_showing = False
        self.current_popup: PopupWidget | None = None 

        # --- Main Layout ---
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.main_layout.setContentsMargins(10, 10, 10, 10) 

        # --- 1. The Bubble ---
        self.bubble = DraggableBubble(ICON_CLOCK, self)
        self.bubble.setFixedSize(56, 56)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10); shadow.setColor(QColor(0,0,0,80)); shadow.setOffset(0, 2)
        self.bubble.setGraphicsEffect(shadow)


        # --- 2. The Side Tray ---
        self.tray = QFrame()
        self.tray.setFixedWidth(224)
        self.tray.setMaximumHeight(0) # Start hidden
        shadow_tray = QGraphicsDropShadowEffect(self)
        shadow_tray.setBlurRadius(10); shadow_tray.setColor(QColor(0,0,0,80)); shadow_tray.setOffset(0, 2)
        self.tray.setGraphicsEffect(shadow_tray)


        # --- Animation ---
        self.animation = QPropertyAnimation(self.tray, b"maximumHeight")
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.setDuration(200)

        # --- Tray Layout & Content ---
        self.tray_layout = QVBoxLayout(self.tray)
        self.tray_layout.setContentsMargins(0, 0, 0, 0)
        self.tray_layout.setSpacing(0)

        self.title_label = QLabel("Select Mode")
        self.tray_layout.addWidget(self.title_label)

        self.mode_list = QListWidget()
        self.mode_list.itemClicked.connect(self.on_mode_selected)
        self.tray_layout.addWidget(self.mode_list)

        # --- Bottom Buttons ---
        self.bottom_bar = QWidget()
        self.bottom_layout = QHBoxLayout()
        
        self.settings_btn = QPushButton(ICON_SETTINGS)
        self.quit_btn = QPushButton(ICON_QUIT)

        for btn in [self.settings_btn, self.quit_btn]:
            btn.setFixedSize(28, 28)

        self.bottom_layout.addWidget(self.settings_btn)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.quit_btn)
        self.bottom_bar.setLayout(self.bottom_layout)
        self.tray_layout.addWidget(self.bottom_bar)

        # Add to main layout
        self.main_layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignRight)
        self.main_layout.addWidget(self.tray, 0, Qt.AlignmentFlag.AlignRight)
        self.setLayout(self.main_layout)

        # --- Apply Theme ---
        self.apply_theme()

        # --- Connect Signals ---
        self.bubble.clicked.connect(self.toggle_tray)
        self.quit_btn.clicked.connect(self.quit_signal.emit)
        self.settings_btn.clicked.connect(self.open_settings_popup)

    def open_settings_popup(self):
        """Creates and shows the SettingsPopup."""
        if self.settings_popup and self.settings_popup.isVisible():
            print("[UI] Settings popup already open, activating.")
            self.settings_popup.activateWindow()
            self.settings_popup.raise_()
        else:
            print("[UI] Opening settings popup.")
            # Pass the theme manager to the settings window
            self.settings_popup = SettingsPopup(theme_manager=self.theme_manager, parent=self)
            # Connect the signal to refresh bubble
            self.settings_popup.settings_changed_signal.connect(self.on_settings_changed)
            self.settings_popup.show()

    def on_settings_changed(self):
        """SLOT: Called when settings popup saves a change."""
        print("[UI] Settings changed, refreshing bubble...")
        # Refresh theme
        self.colors = self.theme_manager.get_active_theme_colors()
        self.apply_theme()
        # Refresh mode list
        self.refresh_bubble_modes()
        
    def refresh_bubble_modes(self):
        """SLOT to refresh the bubble's mode list when settings change."""
        print("[UI] Refreshing bubble mode list after settings change...")
        modes = config.settings.get("modes", [])
        current_mode_id = config.settings.get("active_mode_id", "mode_001")
        self.populate_modes(modes, current_mode_id)

    def populate_modes(self, modes_list, current_mode_id):
        """SLOT: Fills the mode list in the bubble tray."""
        print("[UI] Populating bubble mode list...")
        self.mode_list.clear()
        self.modes_map.clear()
        for mode in modes_list:
            name = mode.get("name", "Unnamed Mode")
            mode_id = mode.get("id", "")
            self.modes_map[name] = mode_id
            item = QListWidgetItem(name)
            self.mode_list.addItem(item)
            if mode_id == current_mode_id:
                self.mode_list.setCurrentItem(item)
                print(f"[UI] Set active mode in bubble: {name}")

    def on_mode_selected(self, item):
        """User clicked a mode in the bubble tray."""
        mode_name = item.text()
        mode_id = self.modes_map.get(mode_name)
        if mode_id:
            print(f"[UI] Mode selected in bubble: {mode_name} (ID: {mode_id})")
            self.mode_changed_signal.emit(mode_id)
        self.toggle_tray() # Close tray

    def toggle_tray(self):
        """Opens/closes the side tray."""
        print("[UI] Bubble clicked, toggling tray.")
        self.is_tray_open = not self.is_tray_open
        if self.is_tray_open:
            self.animation.setStartValue(0)
            self.animation.setEndValue(250) # Target height
        else:
            # Need to get current height before starting animation
            current_height = self.tray.size().height() # type: ignore
            self.animation.setStartValue(current_height)
            self.animation.setEndValue(0)
        self.animation.start()

    def apply_theme(self):
        """Applies the loaded theme colors to the bubble UI."""
        c = self.colors
        # FIX: Use single quotes inside f-strings for Python 3.11 compatibility
        self.bubble.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('surface', '#FFF')}; border: 1px solid {c.get('border', '#E0E0E0')};
                border-radius: 28px; font-size: 28px; color: {c.get('primary', '#3B82F6')};
            }}
            QPushButton:hover {{ background-color: {c.get('hover_bg', '#F3F4F6')}; }}
        """)
        self.tray.setStyleSheet(f"""
            QFrame {{
                background-color: {c.get('surface', '#F9FAFB')}; 
                border-radius: 8px; border: 1px solid {c.get('border', '#E5E7EB')};
            }}
        """)
        self.title_label.setStyleSheet(f"""
            QLabel {{ font-size: 14px; font-weight: 600; padding: 8px;
                     border-bottom: 1px solid {c.get('border', '#E5E7EB')}; color: {c.get('text_primary', '#1F2937')}; }}
        """)
        self.mode_list.setStyleSheet(f"""
            QListWidget {{ border: none; background-color: transparent; color: {c.get('text_secondary', '#374151')}; }}
            QListWidget::item {{ padding: 10px 12px; }}
            QListWidget::item:hover {{ background-color: {c.get('hover_bg', '#F3F4F6')}; }}
            QListWidget::item:selected {{ background-color: {c.get('selected_bg', '#EFF6FF')}; color: {c.get('selected_text', '#1D4ED8')}; font-weight: 600; }}
        """)
        self.bottom_bar.setStyleSheet(f"border-top: 1px solid {c.get('border', '#E5E7EB')}; padding: 4px;")
        for btn in [self.settings_btn, self.quit_btn]:
            btn.setStyleSheet(f"""
                QPushButton {{ border: none; font-size: 18px; color: {c.get('text_secondary', '#4B5563')}; padding: 0; }}
                QPushButton:hover {{ background-color: {c.get('hover_bg', '#E5E7EB')}; border-radius: 4px; }}
            """)


    # --- Popup Handling Logic ---
    def show_reminder_popup(self, title, message, reminder_type, duration_sec):
        print(f"[UI] Received popup request: {title}")
        self.popup_queue.append((title, message, duration_sec))
        self.process_popup_queue()

    def process_popup_queue(self):
        if self.is_popup_showing or not self.popup_queue:
            return
        self.is_popup_showing = True
        title, message, duration_sec = self.popup_queue.pop(0)
        print(f"[UI] Showing popup: {title} for {duration_sec}s")
        # Pass theme colors to the popup
        self.current_popup = PopupWidget(title, message, duration_sec, self.colors)
        self.current_popup.closed.connect(self.on_popup_closed)
        self.current_popup.show()

    def on_popup_closed(self):
        print("[UI] Popup closed.")
        self.is_popup_showing = False
        self.current_popup = None # Clear reference
        QTimer.singleShot(50, self.process_popup_queue)

    # --- NEW: Sound and TTS Slots ---
    def on_play_audio(self, sound_file_name):
        """SLOT: Plays a sound file from the data/sounds folder."""
        try:
            # Construct path to sound file
            sound_path = os.path.join(config.DATA_DIR, 'sounds', sound_file_name)
            
            if not os.path.exists(sound_path):
                print(f"[UI Error] Sound file not found: {sound_path}")
                return

            print(f"[UI] Playing sound: {sound_file_name}")
            self.player.setSource(QUrl.fromLocalFile(sound_path))
            self.player.play()
        except Exception as e:
            print(f"[UI Error] Could not play sound: {e}")

    def on_speak_text(self, title, message):
        """SLOT: Adds a text-to-speech request to the queue."""
        full_text = f"{title}. {message}"
        print(f"[UI] Adding to TTS queue: {full_text}")
        self.tts_queue.append(full_text)
        self.process_tts_queue() # Try to process the queue
        try:
            self.tts.say(full_text)
        except Exception as e:
            print(f"[UI Error] Could not speak text: {e}")

    def process_tts_queue(self):
        """
        Processes the next item in the TTS queue if not already speaking.
        """
        if self.is_speaking or not self.tts_queue:
            # Don't interrupt, or nothing to say
            return

        self.is_speaking = True
        # Get the next message from the front of the line
        full_text = self.tts_queue.pop(0)
        
        print(f"[UI] Speaking text: {full_text}")
        try:
            self.tts.say(full_text)
        except Exception as e:
            print(f"[UI Error] Could not speak text: {e}")
            self.is_speaking = False # Reset state on error

    def on_tts_finished(self, state):
        """
        SLOT: Called when the TTS engine's state changes.
        We use this to process the next item when speech is done.
        """
        if state == QTextToSpeech.State.Ready: # This means it just finished speaking
            self.is_speaking = False
            # Check if there's more to say
            self.process_tts_queue()


# --- Self-Test ---
if __name__ == "__main__":
    # Fallback needs os module
    if 'os' not in locals() and 'os' not in globals():
        import os

    app = QApplication(sys.argv)
    # Test BubbleWidget directly
    bubble_window = BubbleWidget(app)
    bubble_window.show()

    # Add dummy modes for testing
    dummy_modes = [
        {"id": "mode_001", "name": "Work", "is_default": True},
        {"id": "mode_002", "name": "Focus"},
    ]
    bubble_window.populate_modes(dummy_modes, "mode_001")

    sys.exit(app.exec())

