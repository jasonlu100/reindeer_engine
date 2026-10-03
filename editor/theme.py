"""Modern UI theming for the Reindeer editor.

Applies Qt's ``Fusion`` style plus a hand-written QSS stylesheet so the
editor looks like a contemporary dark (or light) IDE instead of the native
Windows 95-ish widgets.  The active theme is chosen from
``editor.settings`` and can be toggled live from the *Settings* menu.
"""
from __future__ import annotations

# Shared accent palette -----------------------------------------------------
ACCENT = "#4a90e2"
ACCENT_HOVER = "#5b9fe8"
ACCENT_PRESS = "#3a7bc8"

_DARK_QSS = f"""
QMainWindow {{
    background: #15161b;
    color: #e6e6ec;
}}
QWidget {{
    background: #15161b;
    color: #e6e6ec;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}}
QDockWidget {{
    border: 1px solid #2a2c36;
    border-radius: 6px;
    titlebar-close-icon: none;
    titlebar-normal-icon: none;
}}
QDockWidget::title {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #262936, stop:1 #1d1f29);
    padding: 7px 10px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #e6e6ec;
    font-weight: 600;
}}
QToolBar {{
    background: #1b1d25;
    border: none;
    spacing: 6px;
    padding: 4px;
    border-bottom: 1px solid #2a2c36;
}}
QToolButton, QPushButton {{
    background: #2a2d3a;
    color: #e6e6ec;
    border: 1px solid #353949;
    border-radius: 6px;
    padding: 6px 12px;
}}
QToolButton:hover, QPushButton:hover {{
    background: #343849;
    border-color: {ACCENT};
}}
QToolButton:pressed, QPushButton:pressed {{
    background: {ACCENT_PRESS};
}}
QPushButton:disabled {{
    color: #6b6e7a;
    background: #23252f;
}}
QMenuBar {{
    background: #1b1d25;
    border-bottom: 1px solid #2a2c36;
    padding: 2px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 5px 10px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background: #343849;
}}
QMenu {{
    background: #1f222c;
    border: 1px solid #2a2c36;
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 22px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QMenu::indicator {{
    width: 14px; height: 14px;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: #20222c;
    border: 1px solid #353949;
    border-radius: 5px;
    padding: 5px 7px;
    color: #e6e6ec;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    border: none;
    background: #2a2d3a;
    width: 16px;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QTreeWidget, QListWidget, QTextEdit, QScrollArea, QPlainTextEdit {{
    background: #1a1c24;
    border: 1px solid #2a2c36;
    border-radius: 6px;
    alternate-background-color: #1e2029;
}}
QTreeWidget::item, QListWidget::item {{
    padding: 4px 6px;
    border-radius: 3px;
}}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {ACCENT};
    color: #ffffff;
}}
QHeaderView::section {{
    background: #262936;
    border: none;
    padding: 5px;
    color: #cfd2dd;
}}
QTextEdit {{
    color: #c8e6c9;
}}
QScrollBar:vertical {{
    background: #1a1c24;
    width: 12px;
}}
QScrollBar::handle {{
    background: #353949;
    border-radius: 6px;
    min-height: 24px;
}}
QScrollBar::handle:hover {{ background: #44495c; }}
QScrollBar:horizontal {{
    background: #1a1c24;
    height: 12px;
}}
QScrollBar::handle:horizontal {{
    background: #353949;
    border-radius: 6px;
    min-width: 24px;
}}
QLabel {{
    background: transparent;
}}
QStatusBar {{
    background: #1b1d25;
    border-top: 1px solid #2a2c36;
    color: #9aa0b0;
}}
QGroupBox {{
    border: 1px solid #2a2c36;
    border-radius: 6px;
    margin-top: 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {ACCENT};
}}
"""

_LIGHT_QSS = f"""
QMainWindow {{ background: #f4f5f7; color: #20232a; }}
QWidget {{
    background: #f4f5f7;
    color: #20232a;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}}
QDockWidget {{
    border: 1px solid #d4d7de;
    border-radius: 6px;
}}
QDockWidget::title {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff, stop:1 #e9ecf1);
    padding: 7px 10px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    color: #20232a;
    font-weight: 600;
}}
QToolBar {{
    background: #eceef2;
    border: none;
    spacing: 6px;
    padding: 4px;
    border-bottom: 1px solid #d4d7de;
}}
QToolButton, QPushButton {{
    background: #ffffff;
    color: #20232a;
    border: 1px solid #d4d7de;
    border-radius: 6px;
    padding: 6px 12px;
}}
QToolButton:hover, QPushButton:hover {{ background: #eef3fb; border-color: {ACCENT}; }}
QToolButton:pressed, QPushButton:pressed {{ background: {ACCENT_PRESS}; color: #fff; }}
QPushButton:disabled {{ color: #aab; background: #f0f1f4; }}
QMenuBar {{ background: #eceef2; border-bottom: 1px solid #d4d7de; padding: 2px; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: 4px; }}
QMenuBar::item:selected {{ background: #dbe6f5; }}
QMenu {{
    background: #ffffff;
    border: 1px solid #d4d7de;
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {ACCENT}; color: #fff; }}
QMenu::indicator {{ width: 14px; height: 14px; }}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: #ffffff;
    border: 1px solid #d4d7de;
    border-radius: 5px;
    padding: 5px 7px;
    color: #20232a;
}}
QTreeWidget, QListWidget, QTextEdit, QScrollArea {{
    background: #ffffff;
    border: 1px solid #d4d7de;
    border-radius: 6px;
    alternate-background-color: #f7f8fa;
}}
QTreeWidget::item, QListWidget::item {{ padding: 4px 6px; border-radius: 3px; }}
QTreeWidget::item:selected, QListWidget::item:selected {{
    background: {ACCENT}; color: #fff;
}}
QHeaderView::section {{
    background: #e9ecf1; border: none; padding: 5px; color: #404656;
}}
QTextEdit {{ color: #205020; background: #ffffff; }}
QScrollBar:vertical {{ background: #f4f5f7; width: 12px; }}
QScrollBar::handle {{ background: #c7cbd4; border-radius: 6px; min-height: 24px; }}
QScrollBar::handle:hover {{ background: #b3b8c4; }}
QScrollBar:horizontal {{ background: #f4f5f7; height: 12px; }}
QScrollBar::handle:horizontal {{ background: #c7cbd4; border-radius: 6px; min-width: 24px; }}
QLabel {{ background: transparent; }}
QStatusBar {{ background: #eceef2; border-top: 1px solid #d4d7de; color: #5a6072; }}
QGroupBox {{ border: 1px solid #d4d7de; border-radius: 6px; margin-top: 10px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {ACCENT}; }}
"""


_THEMES = {
    "dark": _DARK_QSS,
    "light": _LIGHT_QSS,
}


def get_themes():
    return [("dark", "Dark"), ("light", "Light")]


def apply_theme(app, theme: str = "dark") -> None:
    """Install the Fusion style and the matching stylesheet on ``app``."""
    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    qss = _THEMES.get(theme, _DARK_QSS)
    app.setStyleSheet(qss)
