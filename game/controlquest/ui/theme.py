"""Design tokens (colours, fonts, sizes) and the global Qt stylesheet.

Change the look of the whole game here. Screens and widgets never hard-code
colours: they use the constants below, or the `role` / `variant` properties
that the stylesheet styles.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont

# --- colours -----------------------------------------------------------------
BACKGROUND = "#FFF7EC"  # warm cream behind everything
SURFACE = "#FFFFFF"  # cards, inputs
SURFACE_ALT = "#FFF1DE"  # pressed / subtle fills
LINE = "#EADFCF"  # borders, empty stars
DOT = "#EADCC6"  # background dot grid

INK = "#2B2D42"  # main text
INK_SOFT = "#5C6178"  # secondary text
MUTED = "#9A9FB5"  # captions

PRIMARY = "#FF8A65"  # coral: main buttons, the plan line
PRIMARY_HOVER = "#FF774F"
PRIMARY_PRESSED = "#E9643E"

BALL = "#4D96FF"
BALL_DARK = "#2F6FD6"
STAR = "#FFC93C"
STAR_DARK = "#E8A90C"
BLOCK = "#C9BBA8"  # obstacles
BLOCK_DARK = "#A8977F"

SUCCESS = "#4CBF6B"
WARNING = "#FFA94D"
DANGER = "#FF6B6B"
NEUTRAL = "#B8BCCB"
LOCKED = "#D9D2C7"

# one accent per level card (key used in levels/*.py)
ACCENTS = {
    "coral": "#FF8A65",
    "sky": "#4FB3E8",
    "lilac": "#A98BEB",
    "mint": "#43B581",
    "sun": "#F2B51D",
}

# --- shapes and fonts ----------------------------------------------------------
RADIUS_CARD = 22
RADIUS_BUTTON = 16
FONT_FAMILIES = ["Nunito", "Segoe UI", "Helvetica Neue", "Arial"]


def qcolor(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def accent(key: str) -> str:
    return ACCENTS.get(key, PRIMARY)


def font(size_px: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Font for custom painting (QPainter), consistent with the stylesheet."""
    f = QFont()
    f.setFamilies(FONT_FAMILIES)
    f.setPixelSize(round(size_px))
    f.setWeight(weight)
    return f


def app_font() -> QFont:
    return font(14)


def stylesheet() -> str:
    """Global stylesheet. Widgets opt in with setProperty('role'|'variant', ...)."""
    return f"""
    QWidget {{ color: {INK}; }}
    QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QMainWindow {{ background: {BACKGROUND}; }}

    /* text roles */
    QLabel[role="title"]    {{ font-size: 50px; font-weight: 800; }}
    QLabel[role="heading"]  {{ font-size: 28px; font-weight: 800; }}
    QLabel[role="subheading"] {{ font-size: 19px; font-weight: 700; }}
    QLabel[role="subtitle"] {{ font-size: 18px; color: {INK_SOFT}; }}
    QLabel[role="body"]     {{ font-size: 15px; color: {INK_SOFT}; }}
    QLabel[role="quote"]    {{ font-size: 20px; font-style: italic; color: {INK}; }}
    QLabel[role="caption"]  {{ font-size: 13px; color: {MUTED}; }}
    QLabel[role="tag"] {{
        font-size: 12px; font-weight: 700; color: {INK_SOFT};
        background: {SURFACE_ALT}; border-radius: 10px; padding: 3px 10px;
    }}

    /* buttons */
    QPushButton {{
        font-size: 16px; font-weight: 700; color: {INK};
        background: {SURFACE}; border: 2px solid {LINE};
        border-radius: {RADIUS_BUTTON}px; padding: 9px 24px;
    }}
    QPushButton:hover   {{ border-color: {PRIMARY}; }}
    QPushButton:pressed {{ background: {SURFACE_ALT}; }}
    QPushButton:focus   {{ border-color: {BALL}; }}
    QPushButton:disabled {{ color: {MUTED}; background: {SURFACE_ALT}; border-color: {LINE}; }}

    QPushButton[variant="primary"] {{
        color: white; background: {PRIMARY}; border: none;
        border-bottom: 4px solid {PRIMARY_PRESSED};
    }}
    QPushButton[variant="primary"]:hover   {{ background: {PRIMARY_HOVER}; }}
    QPushButton[variant="primary"]:pressed {{ border-bottom-width: 1px; margin-top: 3px; }}
    QPushButton[variant="primary"]:disabled {{
        background: {LOCKED}; border-bottom-color: {BLOCK}; color: white;
    }}

    QPushButton[variant="ghost"] {{
        background: transparent; border: none; color: {INK_SOFT}; padding: 6px 14px;
    }}
    QPushButton[variant="ghost"]:hover {{ color: {INK}; background: {SURFACE_ALT}; }}

    QPushButton[variant="danger"] {{ color: {DANGER}; }}
    QPushButton[variant="danger"]:hover {{ border-color: {DANGER}; }}

    QPushButton[scale="large"] {{
        font-size: 20px; padding: 12px 32px; border-radius: 20px;
    }}

    /* containers */
    QFrame[role="card"] {{
        background: {SURFACE}; border: 2px solid {LINE}; border-radius: {RADIUS_CARD}px;
    }}
    QFrame[role="card"] QLabel {{ background: transparent; }}
    QFrame[role="card"] QLabel[role="tag"] {{ background: {SURFACE_ALT}; }}
    QFrame[role="pill"] {{
        background: {SURFACE}; border: 2px solid {LINE}; border-radius: 15px;
    }}
    QFrame[role="divider"] {{ background: {LINE}; max-height: 2px; min-height: 2px; border: none; }}

    /* inputs */
    QLineEdit {{
        font-size: 15px; background: {SURFACE}; border: 2px solid {LINE};
        border-radius: 12px; padding: 8px 12px; selection-background-color: {BALL};
    }}
    QLineEdit:focus {{ border-color: {BALL}; }}
    QLineEdit[role="knob_value"] {{
        font-size: 17px; font-weight: 800; padding: 3px 8px; border-radius: 10px;
    }}
    QLineEdit[role="knob_value"]:disabled {{ color: {MUTED}; background: {SURFACE_ALT}; }}

    QSlider {{ min-height: 26px; }}
    QSlider::groove:horizontal {{ height: 8px; background: {LINE}; border-radius: 4px; }}
    QSlider::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 4px; }}
    QSlider::handle:horizontal {{
        background: {SURFACE}; border: 3px solid {PRIMARY};
        width: 14px; height: 14px; margin: -6px 0; border-radius: 10px;
    }}
    QSlider::handle:horizontal:hover {{ border-color: {PRIMARY_PRESSED}; }}
    QSlider::sub-page:horizontal:disabled {{ background: {LOCKED}; }}
    QSlider::handle:horizontal:disabled {{ border-color: {LOCKED}; }}

    QComboBox {{
        font-size: 15px; font-weight: 700; background: {SURFACE}; border: 2px solid {LINE};
        border-radius: 12px; padding: 6px 12px; min-width: 56px;
    }}
    QComboBox:hover {{ border-color: {PRIMARY}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE}; border: 2px solid {LINE}; selection-background-color: {SURFACE_ALT};
        selection-color: {INK}; outline: none;
    }}

    QSpinBox {{
        font-size: 15px; font-weight: 700; background: {SURFACE}; border: 2px solid {LINE};
        border-radius: 10px; padding: 4px 8px; min-width: 64px;
    }}
    QSpinBox:focus {{ border-color: {BALL}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
    QScrollBar::handle:vertical {{ background: {LINE}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QToolTip {{
        color: white; background: {INK}; border: none; padding: 6px 10px; font-size: 13px;
    }}
    QMessageBox {{ background: {SURFACE}; }}
    QMessageBox QLabel {{ font-size: 15px; }}
    QMessageBox QPushButton {{ padding: 8px 20px; min-width: 70px; }}
    """
