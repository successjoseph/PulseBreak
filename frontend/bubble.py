"""
This file creates the floating bubble UI AND the settings popup.
It is now designed to be imported and run by run.py.
It emits signals to the backend and receives data to populate itself.
"""

import sys
import uuid # For generating unique mode IDs
from functools import partial # For connecting signals with arguments

from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QFrame, QHBoxLayout,
    QGraphicsDropShadowEffect, QStackedWidget, QScrollArea,
    QCheckBox, QSpinBox, QComboBox, QGridLayout, QTextEdit,
    QInputDialog, QMessageBox # Added for Add/Delete modes
)
from PyQt6.QtCore import (Qt, QPoint, QTimer, QPropertyAnimation, QEasingCurve,
                          QRect, QSize, pyqtSignal, QObject, QRectF) # Added QRectF
# Import QPaintEvent for type hinting
# Correct import for TextWordWrap is Qt.TextFlag
from PyQt6.QtGui import QColor, QPalette, QIcon, QPainter, QPen, QMouseEvent, QGuiApplication, QPaintEvent

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

    def __init__(self, title, message, duration_sec):
        super().__init__()

        self.title_text = title
        self.message_text = message
        self.duration_ms = max(100, duration_sec * 1000) # Ensure duration is at least 100ms
        self.elapsed_ms = 0

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

        # 1. Dark background (90% opacity)
        bg_color = QColor(31, 41, 55, int(255)) # dark-gray-800
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        # Use float rect for potentially smoother rounded corners
        painter.drawRoundedRect(QRectF(self.rect()), 16.0, 16.0)

        # --- Calculate vertical positions dynamically ---
        content_margin = 40
        available_height = self._popup_height - (2 * content_margin) - 10 # Reserve 10 for timer bar
        title_height_estimate = 50
        message_max_height = available_height - title_height_estimate - 20 # 20px spacing

        # 2. Text (Title)
        painter.setPen(QColor("#F9FAFB")) # white/gray-50
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
        painter.setPen(QColor("#E5E7EB")) # Lighter gray for message

        # Center message below title
        msg_y_pos = title_y_pos + title_height_estimate + 20
        msg_rect = QRect(content_margin, msg_y_pos, self._popup_width - (2*content_margin), message_max_height)

        # *** THE FIX IS HERE ***
        # Use Qt.TextFlag.TextWordWrap for word wrapping
        painter.drawText(QRectF(msg_rect),
                         int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap), # Combine flags as int
                         self.message_text)

        # 4. Timer Bar (Orange)
        if self.duration_ms > 0:
            progress = self.elapsed_ms / self.duration_ms
            # Bar width calculation needs to exclude frame margins if the bar is inside the frame
            # Since we paint directly on the widget, use full width
            bar_width = self._popup_width * (1.0 - progress) # Bar shrinks from right to left

            painter.setBrush(QColor("#F97316")) # orange-500
            # Draw from bottom-left, full width initially, shrinking
            painter.drawRect(0, self._popup_height - 10, int(bar_width), 10)

    def close_popup(self):
        self.closed.emit()
        self.close()


# --- MERGED Settings Popup Widget ---
class SettingsPopup(QWidget):
    def __init__(self, parent=None): # Accept parent
        super().__init__(parent) # Pass parent
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
        self.main_frame.setStyleSheet("""
            #mainFrame {
                background-color: #1F2937;
                border-radius: 10px;
                border: 1px solid #E5E7EB; /* Light border */
            }
        """)
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
        self.close_button.setStyleSheet("""
            QPushButton { background-color: transparent; border: none; font-size: 16px;
                          color: #F97316; padding: 0; margin: 0; }
            QPushButton:hover { color: #F97316; }
        """)
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
        self.nav_widget.setStyleSheet("#sidebar { background-color: #1F2937; border-right: 1px solid #E5E7EB; border-top-left-radius: 10px; border-bottom-left-radius: 10px; }")
        self.nav_layout = QVBoxLayout(self.nav_widget)
        self.nav_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.nav_layout.setContentsMargins(0, 10, 0, 10)

        self.nav_list = QListWidget()
        self.nav_list.addItem("General"); self.nav_list.addItem("Modes")
        self.nav_list.addItem("Work Apps"); self.nav_list.addItem("Affirmations")
        self.nav_list.addItem("About")
        self.nav_list.setStyleSheet("""
            QListWidget { border: none; background-color: transparent; }
            QListWidget::item { padding: 10px 15px; }
            QListWidget::item:selected { background-color: #EFF6FF; color: #F97316; font-weight: bold; border-left: 3px solid #3B82F6; }
        """)
        self.nav_layout.addWidget(self.nav_list)

        # --- 2. Content Area (Stacked Widget) ---
        self.content_stack = QStackedWidget()
        self.content_stack.setStyleSheet("QStackedWidget { padding: 10px; background-color: transparent; }")

        # Create pages using helper methods
        self.page_general = self._create_general_page()
        self.page_modes, self.modes_layout_container = self._create_modes_page_structure() # Store layout ref
        self.page_apps = self._create_work_apps_page()
        self.page_affirmations = self._create_affirmations_page()
        self.page_about = self._create_about_page()

        # Add pages to stack
        self.content_stack.addWidget(self.page_general)
        self.content_stack.addWidget(self.page_modes)
        self.content_stack.addWidget(self.page_apps)
        self.content_stack.addWidget(self.page_affirmations)
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
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 15px; padding-left: 5px;") # Added padding
        page_layout.addWidget(title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; }") # Match background

        scroll_content = QWidget()
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
        layout.addWidget(self._create_setting_row(
            "Run on Startup", "Auto start when computer turns on.",
            QCheckBox(), g_settings.get("run_on_startup", False)))
        theme_combo = QComboBox(); theme_combo.addItems(["system", "light", "dark"])
        layout.addWidget(self._create_setting_row(
            "Theme", "Choose the app's color theme.",
            theme_combo, g_settings.get("theme", "system")))
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
        add_mode_button = QPushButton(" + Add New Mode")
        add_mode_button.setStyleSheet("""
            QPushButton { background-color: #E0E7FF; color: #F97316; border: none;
                          padding: 8px 12px; border-radius: 6px; font-weight: 600;
                          margin-bottom: 15px; text-align: left; }
            QPushButton:hover { background-color: #1F2937; }
        """)
        add_mode_button.clicked.connect(self.add_new_mode)
        # Insert button *before* the stretch in the content layout
        content_layout.insertWidget(0, add_mode_button) # Insert at the top

        # Keep a reference to the layout where mode cards will go
        self.modes_layout_container = content_layout
        return page, content_layout # Return both page and layout ref

    def _build_mode_cards(self):
        """Builds and adds the mode card widgets to the modes page layout."""
        # Clear existing mode widgets first (excluding the Add button and stretch)
        # Iterate backwards to avoid index issues while removing
        for i in reversed(range(self.modes_layout_container.count())):
            item = self.modes_layout_container.itemAt(i)
            # Check if it's a widget item before getting the widget
            if item is not None and item.widget() is not None:
                widget = item.widget()
                # Don't remove the Add button
                if not isinstance(widget, QPushButton):
                    widget.deleteLater() #type: ignore
            # Check if it's a spacer item before accessing spacerItem
            elif item is not None and item.spacerItem() is not None:
                 # Keep the stretch spacer at the end
                 pass
            elif item is not None: # Catch other layout items if necessary
                # Potentially remove other layout items if they aren't the stretch
                # For now, assume only widgets and the final stretch exist besides the button
                pass


        modes = config.settings.get("modes", [])
        self.mode_widgets = {} # Store refs if needed later {mode_id: widget}

        for index, mode in enumerate(modes):
            mode_id = mode.get("id")
            if not mode_id: continue # Skip modes without ID

            mode_widget = QFrame()
            mode_widget.setObjectName(f"card_{mode_id}") # Unique object name
            mode_widget.setFrameShape(QFrame.Shape.StyledPanel)
            mode_widget.setStyleSheet("""
                QFrame { background-color: #1F2937; border: 1px solid #E5E7EB;
                         border-radius: 5px; padding: 10px; margin-bottom: 10px; }
            """)
            mode_layout = QGridLayout(mode_widget)

            # --- Mode Name and Delete Button ---
            name_layout = QHBoxLayout()
            mode_name_label = QLabel(mode.get("name", "Unnamed Mode"))
            mode_name_label.setStyleSheet("font-size: 14px; font-weight: bold;")
            name_layout.addWidget(mode_name_label)
            name_layout.addStretch()

            delete_button = QPushButton(ICON_DELETE)
            delete_button.setFixedSize(24, 24)
            delete_button.setStyleSheet("""
                QPushButton { color: #EF4444; border: none; background: transparent; font-size: 16px; padding: 0;}
                QPushButton:hover { color: #DC2626; }
            """)
            # Use partial to pass mode_id to the delete function
            delete_button.clicked.connect(partial(self.delete_mode, mode_id))
            name_layout.addWidget(delete_button)

            mode_layout.addLayout(name_layout, 0, 0, 1, 5) # Span 5 columns

            # Reminder Headers
            mode_layout.addWidget(QLabel("Reminder"), 1, 0)
            mode_layout.addWidget(QLabel("Enabled"), 1, 1)
            mode_layout.addWidget(QLabel("Interval (min)"), 1, 2)
            mode_layout.addWidget(QLabel("Delivery"), 1, 3)
            mode_layout.addWidget(QLabel("Duration (sec)"), 1, 4)

            row = 2
            # Use reminder library order for consistency if possible
            reminder_keys = config.DEFAULT_SETTINGS['reminder_library'].keys()
            mode_reminders = mode.get("reminders", {})

            for r_id in reminder_keys:
                if r_id in mode_reminders:
                    r_settings = mode_reminders[r_id]
                    r_name = config.settings.get("reminder_library", {}).get(r_id, {}).get("name", r_id)

                    toggle = QCheckBox(); interval_spin = QSpinBox(); interval_spin.setRange(1, 240)
                    delivery_combo = QComboBox(); delivery_combo.addItems(["popup", "audio"])
                    duration_spin = QSpinBox(); duration_spin.setRange(0, 300); duration_spin.setSuffix(" sec")

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

            # Insert the mode widget before the stretch item
            # Find the stretch item index (should be the last one)
            stretch_index = self.modes_layout_container.count() -1
            self.modes_layout_container.insertWidget(stretch_index, mode_widget)
            self.mode_widgets[mode_id] = mode_widget # Store reference


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
        # Add a save button
        save_button = QPushButton("Save Affirmations")
        save_button.clicked.connect(self.save_affirmations)
        layout.addWidget(save_button, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()
        return page

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
        row_widget.setStyleSheet("QFrame#settingRow { border-bottom: 1px solid #eee; padding-bottom: 10px; margin-bottom: 10px; }")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0) # No margins for row layout

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0,0,0,0)
        name_label = QLabel(name)
        # name_label.setStyleSheet("font-weight: bold;") # Removed style
        desc_label = QLabel(description)
        # desc_label.setStyleSheet("color: #555;") # Removed style
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
            widget.setCurrentText(str(current_value))
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
            # Copy reminders structure from the FIRST default setting mode template
            # Ensure DEFAULT_SETTINGS is accessible or passed appropriately
            base_reminders = config.DEFAULT_SETTINGS['modes'][0]['reminders']
            new_reminders = {k: v.copy() for k, v in base_reminders.items()} # Deep copy needed

            new_mode = {
                "id": new_mode_id,
                "name": mode_name,
                "is_default": False,
                "reminders": new_reminders
            }
            config.settings['modes'].append(new_mode)
            config.save_settings(config.settings)
            self.refresh_modes_page()
            # Find the BubbleWidget parent and tell it to refresh its mode list
            bubble_parent = self.parent()
            if isinstance(bubble_parent, BubbleWidget):
                 bubble_parent.populate_modes(config.settings['modes'], config.settings.get("active_mode_id", "mode_001"))


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
            # Check if deleted mode was the active one, if so, switch to default
            active_mode_id = config.settings.get("active_mode_id")
            if active_mode_id == mode_id_to_delete:
                 # Find new default
                 default_mode_id = next((m['id'] for m in config.settings['modes'] if m.get('is_default')), config.settings['modes'][0]['id'])
                 config.settings['active_mode_id'] = default_mode_id
                 # TODO: Signal backend about mode change? BubbleWidget needs update too.

            config.save_settings(config.settings)
            self.refresh_modes_page()
            # Find the BubbleWidget parent and tell it to refresh its mode list
            bubble_parent = self.parent()
            if isinstance(bubble_parent, BubbleWidget):
                 bubble_parent.populate_modes(config.settings['modes'], config.settings.get("active_mode_id", "mode_001"))


    def refresh_modes_page(self):
        """Clears and rebuilds the mode cards in the UI."""
        print("[UI] Refreshing modes page UI...")
        self._build_mode_cards()

    # --- Save Settings Logic ---
    def save_general_setting(self):
        """Saves changes made on the General Settings page."""
        sender = self.sender()
        if not sender: return

        setting_name = sender.objectName().replace('_widget', '')
        new_value = None

        if isinstance(sender, QCheckBox):
            new_value = sender.isChecked()
            # Map simple name to nested structure in JSON
            if setting_name == "run_on_startup": config.settings['global_settings']['run_on_startup'] = new_value
        elif isinstance(sender, QComboBox):
            new_value = sender.currentText()
            if setting_name == "theme": config.settings['global_settings']['theme'] = new_value
        elif isinstance(sender, QSpinBox):
            new_value = sender.value()
            if setting_name == "afk_threshold": config.settings['global_settings']['afk_threshold_sec'] = new_value

        if new_value is not None:
            print(f"[UI] Saving General Setting: {setting_name} = {new_value}")
            config.save_settings(config.settings)
            # TODO: Add logic to notify backend if certain settings change (e.g., AFK threshold)

    def save_affirmations(self):
        """Saves the affirmations from the text edit."""
        affirmations_text = self.affirmations_text_edit.toPlainText()
        affirmations_list = [line.strip() for line in affirmations_text.splitlines() if line.strip()]
        config.settings['affirmation_library'] = affirmations_list
        config.save_settings(config.settings)
        print(f"[UI] Saved {len(affirmations_list)} affirmations.")
        QMessageBox.information(self, "Saved", "Affirmations updated successfully.")

    # TODO: Add save logic for Mode settings when controls are changed.
    # This will involve connecting signals from all the checkboxes, spinboxes,
    # and comboboxes within each mode card to a new `save_mode_setting` method.


# --- Main Bubble Widget ---
class BubbleWidget(QWidget):
    # --- Signals from Frontend to Backend ---
    mode_changed_signal = pyqtSignal(str)     # Emits the mode_id
    # settings_signal REMOVED
    quit_signal = pyqtSignal()                # Emits when quit is clicked

    def __init__(self, app_instance=None):
        super().__init__()

        self.app = app_instance
        self.settings_popup: SettingsPopup | None = None # Reference to settings

        # --- Window Setup ---
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(256, 300) # w=224+padding, h=tray+bubble

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
        self.modes_map = {} # To store "Mode Name": "mode_id_123"
        self.popup_queue = [] # To queue reminders
        self.is_popup_showing = False
        self.current_popup: PopupWidget | None = None # Keep reference

        # --- Main Layout ---
        self.main_layout = QVBoxLayout()
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.main_layout.setContentsMargins(10, 10, 10, 10) # Add padding for shadow

        # --- 1. The Bubble ---
        self.bubble = DraggableBubble(ICON_CLOCK, self)
        self.bubble.setFixedSize(56, 56)
        self.bubble.setStyleSheet("""
            QPushButton {
                background-color: #1F2937; border: 1px solid #E0E0E0;
                border-radius: 28px; font-size: 28px; color: #F97316;
            }
            QPushButton:hover { background-color: #F97316; }
        """)
        self.bubble.clicked.connect(self.toggle_tray)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10); shadow.setColor(QColor(0,0,0,80)); shadow.setOffset(0, 2)
        self.bubble.setGraphicsEffect(shadow)


        # --- 2. The Side Tray ---
        self.tray = QFrame()
        self.tray.setFixedWidth(224)
        self.tray.setMaximumHeight(0) # Start hidden
        self.tray.setStyleSheet("""
            QFrame {
                background-color: #1F2937; 
                border-radius: 8px; border: 1px solid #E5E7EB;
            }
        """)
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

        title = QLabel("Select Mode")
        title.setStyleSheet("""
            QLabel { font-size: 14px; font-weight: 600; padding: 8px;
                     border-bottom: 1px solid #E5E7EB; #F97316; }
        """)
        self.tray_layout.addWidget(title)

        self.mode_list = QListWidget()
        self.mode_list.setStyleSheet("""
            QListWidget { border: none; background-color: transparent; }
            QListWidget::item { padding: 10px 12px; color: #F97316; }
            QListWidget::item:hover { background-color: #F3F4F6; }
            QListWidget::item:selected { background-color: #EFF6FF; color: #1D4ED8; font-weight: 600; }
        """)
        self.mode_list.itemClicked.connect(self.on_mode_selected)
        self.tray_layout.addWidget(self.mode_list)

        # --- Bottom Buttons ---
        self.bottom_bar = QWidget()
        self.bottom_layout = QHBoxLayout()
        self.bottom_bar.setStyleSheet("border-top: 1px solid #E5E7EB; padding: 4px;")

        self.settings_btn = QPushButton(ICON_SETTINGS)
        self.quit_btn = QPushButton(ICON_QUIT)

        for btn in [self.settings_btn, self.quit_btn]:
            btn.setFixedSize(28, 28)
            btn.setStyleSheet("""
                QPushButton { border: none; font-size: 18px; color: #4B5563; padding: 0; } /* Remove padding */
                QPushButton:hover { background-color: #E5E7EB; border-radius: 4px; }
            """)

        self.bottom_layout.addWidget(self.settings_btn)
        self.bottom_layout.addStretch()
        self.bottom_layout.addWidget(self.quit_btn)
        self.bottom_bar.setLayout(self.bottom_layout)
        self.tray_layout.addWidget(self.bottom_bar)

        # Add to main layout
        self.main_layout.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignRight)
        self.main_layout.addWidget(self.tray, 0, Qt.AlignmentFlag.AlignRight)
        self.setLayout(self.main_layout)

        # --- Connect Signals ---
        self.quit_btn.clicked.connect(self.quit_signal.emit)
        # Connect settings button to open the merged popup
        self.settings_btn.clicked.connect(self.open_settings_popup)

    def open_settings_popup(self):
        """Creates and shows the SettingsPopup."""
        # Check if already open and bring to front
        if self.settings_popup and self.settings_popup.isVisible():
            print("[UI] Settings popup already open, activating.")
            self.settings_popup.activateWindow()
            self.settings_popup.raise_()
        else:
            print("[UI] Opening settings popup.")
            self.settings_popup = SettingsPopup(self) # Pass self as parent
            self.settings_popup.show()

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
            # FIX Pylance error
            current_height = self.tray.size().height() # Use .size().height()
            self.animation.setStartValue(current_height)
            self.animation.setEndValue(0)
        self.animation.start()


    # --- Popup Handling Logic (Unchanged) ---
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
        self.current_popup = PopupWidget(title, message, duration_sec)
        self.current_popup.closed.connect(self.on_popup_closed)
        self.current_popup.show()

    def on_popup_closed(self):
        print("[UI] Popup closed.")
        self.is_popup_showing = False
        self.current_popup = None # Clear reference
        # Use QTimer to delay processing next popup slightly,
        # helps prevent immediate reopening issues sometimes
        QTimer.singleShot(50, self.process_popup_queue)


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