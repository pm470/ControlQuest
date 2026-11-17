"""Design tokens (colours, fonts, sizes) and the global Qt stylesheet.

Change the look of the whole game here. Screens and widgets never hard-code
colours: they use the constants below, or the `role` / `variant` properties
that the stylesheet styles.

The look (AGENTS.md section 10, "Design rules"): warm cream background with a dot
grid; white rounded TILES that stand on a soft darker "lip" instead of having an
outline; inside a tile, tonal WELLS (no boxes in boxes); no outlines anywhere,
only fills and lips.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QColor, QFont

# --- colours -----------------------------------------------------------------
BACKGROUND = "#FFF7EC"  # warm cream behind everything
SURFACE = "#FFFFFF"  # tiles (cards)
SURFACE_ALT = "#FFF1DE"  # tonal fills: wells, inputs, secondary buttons
WELL = SURFACE_ALT  # an inset area inside a tile (playbar, value fields, slider tracks)
WELL_HOVER = "#FFE8CC"
LIP = "#EBDBC4"  # the soft "lip" under tiles and buttons (instead of outlines)
LINE = "#EADFCF"  # dividers, empty stars
DOT = "#EADCC6"  # background dot grid
FIELD = "#FFF8EE"  # the map board
FIELD_GRID = "#F3E5D0"  # grid lines on the map board
FOCUS = "#A9CBFF"  # soft ring around a focused input

INK = "#2B2D42"  # main text
INK_SOFT = "#5C6178"  # secondary text
MUTED = "#9A9FB5"  # captions

PRIMARY = "#FF8A65"  # coral: main buttons, the plan line
PRIMARY_HOVER = "#FF774F"
PRIMARY_PRESSED = "#E9643E"  # also the lip under primary buttons
PRIMARY_INK = "#C2502F"  # coral text on white (eyebrows, links)

BALL = "#4D96FF"
BALL_DARK = "#2F6FD6"
STAR = "#FFC93C"
STAR_DARK = "#E8A90C"
BLOCK = "#C9BBA8"  # obstacles
BLOCK_DARK = "#A8977F"
WAYPOINT = "#A98BEB"  # lilac diamonds (Level 3)

SUCCESS = "#4CBF6B"
SUCCESS_INK = "#2F8A55"  # green text on white
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
# darker shade of each accent: the lip under level badges and tiles
ACCENT_LIPS = {
    "coral": "#E9643E",
    "sky": "#2E92C4",
    "lilac": "#8667D0",
    "mint": "#2F9461",
    "sun": "#CF9412",
}


@dataclass(frozen=True)
class KnobColor:
    """Colour of one knob: its slider, and its symbol in the knob list AND in the OCP,
    so the player sees which part of the math a knob changes."""
    main: str  # slider fill
    ink: str  # symbol text (readable on the tint)
    tint: str  # chip background behind the symbol


# knob i of a level gets KNOB_COLORS[i] (order of "knobs" in the level file)
KNOB_COLORS = [
    KnobColor("#FF8A65", "#C2502F", "#FFE3D8"),  # coral
    KnobColor("#4D96FF", "#2C66C4", "#DCE9FF"),  # blue
    KnobColor("#43B581", "#2B7D4F", "#DCF2E4"),  # mint
    KnobColor("#A98BEB", "#7254C7", "#ECE4FB"),  # lilac
    KnobColor("#F2B51D", "#A37406", "#FDF0CC"),  # sun
]


NEW_GLOW = "#FFEAA6"  # soft highlighter behind OCP parts that are new in a level (level intro)


def knob_color(index: int) -> KnobColor:
    return KNOB_COLORS[index % len(KNOB_COLORS)]


# --- shapes and fonts ----------------------------------------------------------
RADIUS_CARD = 26  # tiles
RADIUS_BUTTON = 16
LIP_PX = 5  # height of the lip under a tile (buttons: 3-4)
FONT_FAMILIES = ["Nunito", "Segoe UI", "Helvetica Neue", "Arial"]


def qcolor(hex_color: str, alpha: int = 255) -> QColor:
    c = QColor(hex_color)
    c.setAlpha(alpha)
    return c


def accent(key: str) -> str:
    return ACCENTS.get(key, PRIMARY)


def accent_lip(key: str) -> str:
    return ACCENT_LIPS.get(key, PRIMARY_PRESSED)


def font(size_px: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Font for custom painting (QPainter), consistent with the stylesheet."""
    f = QFont()
    f.setFamilies(FONT_FAMILIES)
    f.setPixelSize(round(size_px))
    f.setWeight(weight)
    return f


def app_font() -> QFont:
    return font(14)


# the dropdown arrow (an image: Qt stylesheets cannot draw one); forward slashes for Qt
CHEVRON = (Path(__file__).resolve().parent / "assets" / "chevron_down.svg").as_posix()


def stylesheet() -> str:
    """Global stylesheet. Widgets opt in with setProperty('role'|'variant'|'scale', ...).

    No outlines: tiles and buttons stand on a lip (a thicker bottom border in a darker
    tone); inputs and wells are tonal fills. A soft blue ring only marks keyboard focus.
    """
    return f"""
    QWidget {{ color: {INK}; }}
    QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QMainWindow {{ background: {BACKGROUND}; }}

    /* text roles */
    QLabel[role="title"]    {{ font-size: 50px; font-weight: 800; }}
    QLabel[role="heading"]  {{ font-size: 28px; font-weight: 800; }}
    QLabel[role="subheading"] {{ font-size: 18px; font-weight: 800; }}
    QLabel[role="subtitle"] {{ font-size: 18px; color: {INK_SOFT}; }}
    QLabel[role="body"]     {{ font-size: 15px; color: {INK_SOFT}; }}
    QLabel[role="goal"]     {{ font-size: 15px; font-weight: 600; color: {INK}; }}
    QLabel[role="quote"]    {{ font-size: 20px; font-style: italic; color: {INK}; }}
    QLabel[role="caption"]  {{ font-size: 13px; color: {MUTED}; }}
    QLabel[role="eyebrow"]  {{ font-size: 13px; font-weight: 800; color: {PRIMARY_INK}; }}
    QLabel[role="stat"]     {{ font-size: 21px; font-weight: 800; color: {INK}; }}
    QLabel[role="tag"] {{
        font-size: 12px; font-weight: 700; color: {INK_SOFT};
        background: {SURFACE_ALT}; border-radius: 10px; padding: 3px 10px;
    }}

    /* buttons: tonal with a lip; primary = coral */
    QPushButton {{
        font-size: 16px; font-weight: 700; color: {INK};
        background: {WELL}; border: none; border-bottom: 3px solid {LIP};
        border-radius: {RADIUS_BUTTON}px; padding: 9px 24px;
    }}
    QPushButton:hover   {{ background: {WELL_HOVER}; }}
    QPushButton:pressed {{ border-bottom-width: 1px; margin-top: 2px; }}
    QPushButton:disabled {{ color: {MUTED}; background: {WELL}; }}

    QPushButton[variant="primary"] {{
        color: white; background: {PRIMARY}; border-bottom: 4px solid {PRIMARY_PRESSED};
    }}
    QPushButton[variant="primary"]:hover   {{ background: {PRIMARY_HOVER}; }}
    QPushButton[variant="primary"]:pressed {{ border-bottom-width: 1px; margin-top: 3px; }}
    QPushButton[variant="primary"]:disabled {{
        background: {LOCKED}; border-bottom-color: {BLOCK}; color: white;
    }}

    QPushButton[variant="ghost"] {{
        background: transparent; border: none; color: {INK_SOFT}; padding: 6px 14px;
    }}
    QPushButton[variant="ghost"]:hover {{ color: {INK}; background: {WELL}; }}
    QPushButton[variant="ghost"]:pressed {{ margin-top: 0px; }}

    QPushButton[variant="link"] {{
        background: transparent; border: none; color: {PRIMARY_INK};
        font-size: 14px; font-weight: 800; padding: 4px 6px;
    }}
    QPushButton[variant="link"]:hover {{ color: {PRIMARY_PRESSED}; }}
    QPushButton[variant="link"]:pressed {{ margin-top: 0px; }}
    QPushButton[variant="link"]:disabled {{ color: {MUTED}; background: transparent; }}

    QPushButton[variant="chip"] {{
        background: {SURFACE}; border-bottom: 2px solid {LIP}; border-radius: 10px;
        font-size: 13px; font-weight: 800; padding: 4px 10px;
    }}
    QPushButton[variant="chip"]:hover {{ background: #FFFBF5; }}
    QPushButton[variant="chip"]:disabled {{ background: {SURFACE}; color: {LOCKED}; }}

    QPushButton[variant="danger"] {{ color: {DANGER}; }}

    QPushButton[scale="large"] {{
        font-size: 20px; padding: 12px 32px; border-radius: 20px;
    }}
    QPushButton[scale="tall"] {{
        font-size: 15px; font-weight: 800; padding: 13px 18px; border-radius: 18px;
    }}

    /* containers: tiles (role "card") stand on a lip; wells are tonal insets */
    QFrame[role="card"] {{
        background: {SURFACE}; border: none; border-bottom: {LIP_PX}px solid {LIP};
        border-radius: {RADIUS_CARD}px;
    }}
    QFrame[role="card"] QLabel {{ background: transparent; }}
    QFrame[role="card"] QLabel[role="tag"] {{ background: {SURFACE_ALT}; }}
    QFrame[role="well"] {{ background: {WELL}; border: none; border-radius: 16px; }}
    QFrame[role="well"] QLabel {{ background: transparent; }}
    QFrame[role="pill"] {{
        background: {SURFACE}; border: none; border-bottom: 3px solid {LIP}; border-radius: 15px;
    }}
    QFrame[role="card"] QFrame[role="pill"] {{ background: {WELL}; border-bottom: none; }}
    QFrame[role="divider"] {{ background: {LINE}; max-height: 2px; min-height: 2px; border: none; }}
    QFrame[role="choice"] {{
        background: {WELL}; border: none; border-bottom: 3px solid {LIP}; border-radius: 14px;
    }}
    QFrame[role="choice"]:hover {{ background: {WELL_HOVER}; }}
    QFrame[role="choice"][selected="true"] {{ background: #FFE6DA; border-bottom-color: {PRIMARY}; }}
    QFrame[role="choice"] QLabel {{ background: transparent; }}

    /* inputs: tonal fills, a soft blue ring when focused */
    QLineEdit {{
        font-size: 15px; background: {WELL}; border: 2px solid transparent;
        border-radius: 12px; padding: 7px 11px; selection-background-color: {BALL};
    }}
    QLineEdit:focus {{ border-color: {FOCUS}; background: {SURFACE}; }}
    QLineEdit[role="knob_value"] {{
        font-size: 16px; font-weight: 800; padding: 3px 8px; border-radius: 10px;
    }}
    QLineEdit[role="knob_value"]:disabled {{ color: {MUTED}; }}

    QSlider {{ min-height: 26px; }}
    QSlider::groove:horizontal {{ height: 10px; background: {WELL}; border-radius: 5px; }}
    QSlider::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 5px; }}
    QSlider::handle:horizontal {{
        background: {SURFACE}; border: 2px solid {LIP};
        width: 18px; height: 18px; margin: -6px 0; border-radius: 11px;
    }}
    QSlider::handle:horizontal:hover {{ border-color: {PRIMARY}; }}
    QSlider::sub-page:horizontal:disabled {{ background: {LOCKED}; }}
    QSlider[role="scrubber"] {{ min-height: 20px; }}
    QSlider[role="scrubber"]::groove:horizontal {{ height: 6px; background: {LIP}; border-radius: 3px; }}
    QSlider[role="scrubber"]::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 3px; }}
    QSlider[role="scrubber"]::handle:horizontal {{
        background: {SURFACE}; border: 2px solid {LIP};
        width: 14px; height: 14px; margin: -6px 0; border-radius: 9px;
    }}
    QSlider[role="scrubber"]::sub-page:horizontal:disabled {{ background: {LIP}; }}

    QComboBox {{
        font-size: 15px; font-weight: 700; background: {WELL}; border: 2px solid transparent;
        border-radius: 12px; padding: 5px 10px; min-width: 56px;
    }}
    QComboBox:hover {{ background: {WELL_HOVER}; }}
    QComboBox:focus {{ border-color: {FOCUS}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{ image: url("{CHEVRON}"); width: 12px; height: 8px; }}
    QComboBox QAbstractItemView {{
        background: {SURFACE}; border: 2px solid {LINE}; selection-background-color: {WELL};
        selection-color: {INK}; outline: none;
    }}

    QSpinBox {{
        font-size: 13px; font-weight: 800; background: {SURFACE}; border: 2px solid transparent;
        border-radius: 10px; padding: 3px 4px; min-width: 36px;
    }}
    QSpinBox:focus {{ border-color: {FOCUS}; }}
    QSpinBox:disabled {{ color: {MUTED}; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}

    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px; }}
    QScrollBar::handle:vertical {{ background: {LIP}; border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

    QToolTip {{
        color: white; background: {INK}; border: none; padding: 6px 10px; font-size: 13px;
    }}
    QMessageBox {{ background: {SURFACE}; }}
    QMessageBox QLabel {{ font-size: 15px; }}
    QMessageBox QPushButton {{ padding: 8px 20px; min-width: 70px; }}
    """
