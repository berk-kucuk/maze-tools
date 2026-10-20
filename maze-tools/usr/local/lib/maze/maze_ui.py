"""maze_ui — shared true-black OLED widget toolkit for Maze GUI apps.

Used by maze-control-center and maze-welcome. Provides the OLED palette, the
true-black Glass panel, sidebar nav buttons, status rows and a copy-command
row — plus the OLED kit (GlassWindow, GlassCard, IconTile, Chip, pill
buttons) that maze-hardware and maze-kernel are built on, drawn in the same
black / faint-white language. Apps add /usr/local/lib/maze to sys.path and
`import maze_ui`.
"""
from __future__ import annotations

import ctypes
import os

import maze_i18n
from maze_i18n import tr

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
    QRegion,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsBlurEffect,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LOGO_PATH = "/usr/share/pixmaps/maze-simple-logo.png"
# Fallbacks so the Maze logo never silently vanishes if the primary file is
# absent (e.g. an older install made before it was added to the deploy list).
_LOGO_CANDIDATES = (
    "/usr/share/pixmaps/maze-simple-logo.png",
    "/usr/share/pixmaps/maze-logo.png",
    "/usr/share/icons/hicolor/scalable/apps/maze.svg",
    "/usr/share/icons/hicolor/256x256/apps/maze.png",
)

# True-black OLED palette.
ACCENT = "rgba(255, 255, 255, 0.95)"
ACCENT_HOVER = "#ffffff"
TEXT = "#f2f3f5"
DIM = "#9aa0aa"
FAINT = "#7a7f88"
PANEL_BLACK = "#060608"
PILL_BG = "rgba(255, 255, 255, 0.06)"
PILL_BG_HOVER = "rgba(255, 255, 255, 0.13)"

OK_GREEN = "#56c271"
BAD_RED = "#e06666"
UNK_GRAY = "#6b7079"
MONO = "monospace"


def enable_kde_blur(winid: int, rects: list[tuple[int, int, int, int]] | None = None) -> None:
    """Ask KWin to blur the desktop behind this (translucent) window.

    `rects` (x, y, w, h in device pixels) limits the blur to that region — a
    rounded window passes its shape so the blur does not show as a square
    behind the transparent corners. None blurs the whole window.
    """
    try:
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        dpy = x11.XOpenDisplay(None)
        if not dpy:
            return
        x11.XInternAtom.restype = ctypes.c_ulong
        atom = x11.XInternAtom(
            ctypes.c_void_p(dpy), b"_KDE_NET_WM_BLUR_BEHIND_REGION", False
        )
        flat = [int(v) for r in (rects or ()) for v in r]
        # Format-32 X properties are arrays of C longs, whatever the arch.
        data = (ctypes.c_long * len(flat))(*flat) if flat else None
        x11.XChangeProperty(
            ctypes.c_void_p(dpy), ctypes.c_ulong(int(winid)), ctypes.c_ulong(atom),
            ctypes.c_ulong(6), 32, 0, data, len(flat),
        )
        x11.XFlush(ctypes.c_void_p(dpy))
        x11.XCloseDisplay(ctypes.c_void_p(dpy))
    except Exception:  # noqa: BLE001
        pass


def _blurred(src: QPixmap, radius: float) -> QPixmap:
    pad = int(radius * 3)
    canvas = QPixmap(src.width() + pad * 2, src.height() + pad * 2)
    canvas.fill(Qt.transparent)
    p = QPainter(canvas)
    p.drawPixmap(pad, pad, src)
    p.end()
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(canvas)
    eff = QGraphicsBlurEffect()
    eff.setBlurRadius(radius)
    item.setGraphicsEffect(eff)
    scene.addItem(item)
    out = QImage(canvas.size(), QImage.Format_ARGB32_Premultiplied)
    out.fill(Qt.transparent)
    pr = QPainter(out)
    scene.render(pr, QRectF(out.rect()), scene.itemsBoundingRect())
    pr.end()
    return QPixmap.fromImage(out)


def logo_pixmap() -> QPixmap:
    """The Maze logo, trying each known path, then a themed-icon fallback."""
    for path in _LOGO_CANDIDATES:
        pm = QPixmap(path)
        if not pm.isNull():
            return pm
    ic = themed_icon("maze", "start-here-kde", "computer")
    return ic.pixmap(QSize(128, 128)) if not ic.isNull() else QPixmap()


def logo_icon() -> QIcon:
    """The Maze logo as a QIcon (for window icons / taskbar)."""
    pm = logo_pixmap()
    return QIcon(pm) if not pm.isNull() else QIcon()


def make_watermark() -> QPixmap | None:
    src = logo_pixmap()
    if src.isNull():
        return None
    src = src.scaled(360, 360, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return _blurred(src, 14)


_icon_theme_ready = False


def _ensure_icon_theme() -> None:
    """Make freedesktop icon lookups work even without full Plasma integration.

    A bare QApplication only searches the Qt resource path (`:/icons`), so
    `QIcon.fromTheme` returns nothing. We append the standard XDG icon dirs and
    fall back to breeze-dark (Maze's icon theme) when no theme is set, while
    leaving an already-configured theme (the user's choice under Plasma) intact.
    """
    global _icon_theme_ready
    if _icon_theme_ready:
        return
    paths = QIcon.themeSearchPaths()
    for p in ("/usr/share/icons",
              os.path.expanduser("~/.local/share/icons"),
              os.path.expanduser("~/.icons")):
        if p not in paths:
            paths.append(p)
    QIcon.setThemeSearchPaths(paths)
    if not QIcon.themeName():
        QIcon.setThemeName("breeze-dark")
    if not QIcon.fallbackThemeName():
        QIcon.setFallbackThemeName("breeze-dark")
    _icon_theme_ready = True


# Every icon is recoloured to this single tint so the UI reads as one coherent
# monochrome set (breeze mixes flat-colour and line icons, which clash otherwise).
ICON_TINT = TEXT


def themed_icon(*names: str) -> QIcon:
    """First non-null icon from the active theme for the given names.

    For each requested name we try its `-symbolic` (monochrome line) variant
    first, so we get a consistent line style wherever breeze ships one and only
    fall back to the flat-colour icon otherwise. Maze ships breeze-dark as the
    icon theme; we set it as the fallback so glyphs resolve even without a full
    Plasma icon-theme context. Returns an empty QIcon if nothing matches.
    """
    _ensure_icon_theme()
    for name in names:
        for candidate in (f"{name}-symbolic", name):
            ic = QIcon.fromTheme(candidate)
            if ic is not None and not ic.isNull():
                return ic
    return QIcon()


def _tint_pixmap(pm: QPixmap, color: str) -> QPixmap:
    """Recolour an icon pixmap to a single flat colour, keeping its alpha shape."""
    if pm.isNull() or not color:
        return pm
    out = QPixmap(pm.size())
    out.setDevicePixelRatio(pm.devicePixelRatio())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.drawPixmap(0, 0, pm)
    p.setCompositionMode(QPainter.CompositionMode_SourceIn)
    p.fillRect(out.rect(), QColor(color))
    p.end()
    return out


def themed_pixmap(names: str | tuple[str, ...], px: int,
                  tint: str | None = ICON_TINT) -> QPixmap:
    """A themed icon rendered to a pixmap and tinted to a uniform colour."""
    ic = themed_icon(*((names,) if isinstance(names, str) else names))
    if ic.isNull():
        return QPixmap()
    pm = ic.pixmap(QSize(px, px))
    return _tint_pixmap(pm, tint) if tint else pm


def icon_label(names: str | tuple[str, ...], px: int = 18,
               tint: str | None = ICON_TINT) -> QLabel:
    """A transparent QLabel showing a uniformly-tinted themed icon."""
    lab = QLabel()
    lab.setStyleSheet("background: transparent;")
    lab.setFixedSize(px, px)
    pm = themed_pixmap(names, px, tint)
    if not pm.isNull():
        lab.setPixmap(pm)
    return lab


def icon_pill(names: str | tuple[str, ...], text: str) -> QWidget:
    """A rounded pill with a themed icon and a line of dim text."""
    pill = QFrame()
    pill.setStyleSheet(f"QFrame {{ background: {PILL_BG}; border-radius: 12px; }}")
    lay = QHBoxLayout(pill)
    lay.setContentsMargins(11, 5, 13, 5)
    lay.setSpacing(8)
    lay.addWidget(icon_label(names, 16))
    lab = QLabel(text)
    lab.setStyleSheet(f"color: {DIM}; background: transparent;")
    lab.setFont(QFont("Sans Serif", 9))
    lay.addWidget(lab)
    return pill


def heading(text: str, size: int = 20) -> QLabel:
    lab = QLabel(text)
    lab.setStyleSheet(f"color: {TEXT}; background: transparent;")
    lab.setFont(QFont("Sans Serif", size, QFont.Bold))
    return lab


def paragraph(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setStyleSheet(f"color: {DIM}; background: transparent;")
    lab.setFont(QFont("Sans Serif", 10))
    return lab


def language_toggle(on_change) -> QWidget:
    """A compact EN | TR segmented switch; calls on_change(code) when changed.

    The active language is highlighted. Selecting the already-active language
    does nothing (no needless rebuild)."""
    cur = maze_i18n.current_language()
    box = QFrame()
    box.setStyleSheet("QFrame { background: transparent; }")
    lay = QHBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    for code, label in (("en", "EN"), ("tr", "TR")):
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(26)
        btn.setCheckable(True)
        btn.setChecked(code == cur)
        active = code == cur
        btn.setStyleSheet(
            f"QPushButton {{ color: {'#0a0a0c' if active else DIM};"
            f" background: {ACCENT if active else PILL_BG}; border: none;"
            " border-radius: 7px; padding: 0 11px; font-size: 9pt;"
            f" font-weight: {'bold' if active else 'normal'}; }}"
            f"QPushButton:hover {{ color: {TEXT if not active else '#0a0a0c'};"
            " background: " + (ACCENT_HOVER if active else PILL_BG_HOVER) + "; }}"
        )
        btn.clicked.connect(
            lambda _checked=False, c=code: (
                None if c == maze_i18n.current_language() else on_change(c)))
        lay.addWidget(btn)
    return box


class Glass(QFrame):
    """Frosted-glass panel: near-black fill + faint glow + corner watermark."""

    def __init__(self, watermark: QPixmap | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._wm = watermark

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 22, 22)
        p.setClipPath(path)
        p.fillPath(path, QColor(0, 0, 0, 250))
        glow = QRadialGradient(r.center().x(), r.top() + 70, r.width() * 0.75)
        glow.setColorAt(0.0, QColor(255, 255, 255, 18))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, glow)
        if self._wm is not None and not self._wm.isNull():
            wm = self._wm
            p.setOpacity(0.07)
            p.drawPixmap(r.right() - wm.width() + 40, r.bottom() - wm.height() + 40, wm)
            p.setOpacity(1.0)
        pen = QPen(QColor(255, 255, 255, 40))
        pen.setWidth(1)
        p.setPen(pen)
        p.setClipping(False)
        p.drawRoundedRect(QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), 22, 22)
        p.end()


class NavButton(QPushButton):
    def __init__(self, icon: str | tuple[str, ...], label: str) -> None:
        super().__init__(f"   {label}")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(42)
        pm = themed_pixmap(icon, 18)
        if not pm.isNull():
            self.setIcon(QIcon(pm))
            self.setIconSize(QSize(18, 18))
        self.setStyleSheet(
            f"""
            QPushButton {{ color: {DIM}; background: transparent; border: none;
                           border-radius: 10px; text-align: left; padding-left: 8px;
                           font-size: 11pt; }}
            QPushButton:hover {{ color: {TEXT}; background: rgba(255,255,255,0.06); }}
            QPushButton:checked {{ color: {TEXT}; background: rgba(255,255,255,0.12);
                                   font-weight: bold; }}
            """
        )


def status_row(label: str, state: bool | None, on_text: str = "Active",
               off_text: str = "Inactive", unk_text: str = "Not available") -> QWidget:
    row = QFrame()
    row.setStyleSheet(f"QFrame {{ background: {PILL_BG}; border-radius: 10px; }}")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(14, 9, 14, 9)
    lay.setSpacing(10)
    color = OK_GREEN if state is True else (BAD_RED if state is False else UNK_GRAY)
    dot = QLabel("●")
    dot.setStyleSheet(f"color: {color}; background: transparent;")
    dot.setFont(QFont("Sans Serif", 12))
    lay.addWidget(dot)
    name = QLabel(tr(label))
    name.setStyleSheet(f"color: {TEXT}; background: transparent;")
    name.setFont(QFont("Sans Serif", 11))
    lay.addWidget(name)
    lay.addStretch(1)
    txt = on_text if state is True else (off_text if state is False else unk_text)
    val = QLabel(tr(txt))
    val.setStyleSheet(f"color: {color}; background: transparent;")
    val.setFont(QFont("Sans Serif", 10, QFont.Bold))
    lay.addWidget(val)
    return row


def info_row(label: str, value: str, good: bool | None = None) -> QWidget:
    """A pill row showing label + free-text value, with an optional status dot."""
    row = QFrame()
    row.setStyleSheet(f"QFrame {{ background: {PILL_BG}; border-radius: 10px; }}")
    lay = QHBoxLayout(row)
    lay.setContentsMargins(14, 9, 14, 9)
    lay.setSpacing(10)
    if good is not None:
        dot = QLabel("●")
        dot.setStyleSheet(
            f"color: {OK_GREEN if good else BAD_RED}; background: transparent;")
        dot.setFont(QFont("Sans Serif", 12))
        lay.addWidget(dot)
    name = QLabel(label)
    name.setStyleSheet(f"color: {TEXT}; background: transparent;")
    name.setFont(QFont("Sans Serif", 11))
    lay.addWidget(name)
    lay.addStretch(1)
    val = QLabel(value)
    val.setStyleSheet(f"color: {DIM}; background: transparent;")
    val.setFont(QFont("Sans Serif", 10))
    lay.addWidget(val)
    return row


class Meter(QFrame):
    """A compact dashboard tile: icon + label, a percent and a thin load bar.

    The bar turns amber/red as load climbs so the dashboard reads at a glance.
    """

    def __init__(self, icon: str, label: str) -> None:
        super().__init__()
        self.setStyleSheet(
            f"QFrame {{ background: {PILL_BG}; border-radius: 12px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 11, 14, 12)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(7)
        top.addWidget(icon_label(icon, 15))
        name = QLabel(label)
        name.setStyleSheet(f"color: {DIM}; background: transparent;")
        name.setFont(QFont("Sans Serif", 9, QFont.Bold))
        top.addWidget(name)
        top.addStretch(1)
        self._val = QLabel("—")
        self._val.setStyleSheet(f"color: {TEXT}; background: transparent;")
        self._val.setFont(QFont("Sans Serif", 11, QFont.Bold))
        top.addWidget(self._val)
        lay.addLayout(top)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(6)
        lay.addWidget(self._bar)

        self._detail = QLabel("")
        self._detail.setStyleSheet(f"color: {FAINT}; background: transparent;")
        self._detail.setFont(QFont("Sans Serif", 8))
        lay.addWidget(self._detail)
        self.update_value(0.0, None)

    def update_value(self, percent: float, detail: str | None) -> None:
        p = max(0.0, min(100.0, percent))
        self._bar.setValue(int(round(p)))
        self._val.setText(f"{p:.0f}%")
        chunk = OK_GREEN if p < 70 else ("#e0a458" if p < 90 else BAD_RED)
        self._bar.setStyleSheet(
            "QProgressBar { background: rgba(255,255,255,0.08); border: none;"
            " border-radius: 3px; }"
            f"QProgressBar::chunk {{ background: {chunk}; border-radius: 3px; }}"
        )
        if detail is not None:
            self._detail.setText(detail)


class CommandRow(QFrame):
    """A row that shows a shell command and a Copy button (no execution)."""

    def __init__(self, label: str, command: str) -> None:
        super().__init__()
        self._command = command
        self.setStyleSheet(f"QFrame {{ background: {PILL_BG}; border-radius: 10px; }}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 8, 10, 8)
        lay.setSpacing(10)

        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel(tr(label))
        name.setStyleSheet(f"color: {TEXT}; background: transparent;")
        name.setFont(QFont("Sans Serif", 10, QFont.Bold))
        cmd = QLabel(command)
        cmd.setStyleSheet(f"color: {FAINT}; background: transparent;")
        cmd.setFont(QFont(MONO, 9))
        cmd.setTextInteractionFlags(Qt.TextSelectableByMouse)
        col.addWidget(name)
        col.addWidget(cmd)
        lay.addLayout(col)
        lay.addStretch(1)

        self._btn = QPushButton(f"⧉  {tr('Copy')}")
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(
            f"""
            QPushButton {{ color: {TEXT}; background: {PILL_BG_HOVER}; border: none;
                           border-radius: 9px; padding: 6px 12px; font-size: 9pt; }}
            QPushButton:hover {{ background: rgba(255,255,255,0.20); }}
            """
        )
        self._btn.clicked.connect(self._copy)
        lay.addWidget(self._btn)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._command)
        self._btn.setText(f"✓  {tr('Copied')}")
        QTimer.singleShot(1600, lambda: self._btn.setText(f"⧉  {tr('Copy')}"))


# --------------------------------------------------------------------------- #
#  OLED kit (maze-hardware, maze-kernel)                                       #
#                                                                              #
#  The same true-black surface as Glass above — near-opaque black, a faint     #
#  top glow, the blurred logo watermark and a thin white rim — plus flat       #
#  cards, icon tiles, status chips and buttons that match the Control Center   #
#  and Welcome. Nothing here is see-through: on an OLED panel the black is     #
#  real black, and the window reads the same on any wallpaper.                 #
# --------------------------------------------------------------------------- #
GLASS_RADIUS = 22
_RED = QColor(BAD_RED)
_GREEN = QColor(OK_GREEN)


def font(size: float, weight: QFont.Weight = QFont.Normal,
         spacing: float = 0.0) -> QFont:
    """Inter when it is installed (Maze ships it), the system sans otherwise."""
    f = QFont()
    f.setFamilies(["Inter", "Noto Sans", "Sans Serif"])
    f.setPointSizeF(size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def label(text: str, size: float, color: str,
          weight: QFont.Weight = QFont.Normal, spacing: float = 0.0) -> QLabel:
    lab = QLabel(text)
    lab.setFont(font(size, weight, spacing))
    lab.setStyleSheet(f"color: {color}; background: transparent;")
    return lab


def caps(text: str) -> str:
    # str.upper() maps Turkish "i" to "I" ("GIZLILIK"); dotted İ first.
    if maze_i18n.current_language() == "tr":
        text = text.replace("i", "İ")
    return text.upper()


def svg_pixmap(path: str, px: int, dpr: float, color: QColor | None = None) -> QPixmap:
    """Render an SVG crisply at the screen's scale, optionally recoloured."""
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.fill(Qt.transparent)
    r = QSvgRenderer(path)
    if r.isValid():
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        r.render(p, QRectF(0, 0, pm.width(), pm.height()))
        if color is not None:
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p.fillRect(pm.rect(), color)
        p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def blur_region(w: int, h: int, dpr: float,
                radius: float = GLASS_RADIUS) -> list[tuple[int, int, int, int]]:
    """A rounded window's shape as X11 rects (device pixels) for enable_kde_blur."""
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w * dpr, h * dpr), radius * dpr, radius * dpr)
    region = QRegion(path.toFillPolygon().toPolygon())
    return [(r.x(), r.y(), r.width(), r.height()) for r in region]


def fit_height(want: int, margin: int = 24) -> int:
    """`want`, or the primary screen's usable height when that is smaller."""
    screen = QApplication.primaryScreen()
    if screen is None:
        return want
    return max(360, min(want, screen.availableGeometry().height() - margin))


def mix(a: QColor, b: QColor, t: float) -> QColor:
    """Linear blend of two colours (alpha included); t=0 is a, t=1 is b."""
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t),
                  int(a.alpha() + (b.alpha() - a.alpha()) * t))


class GlassWindow(Glass):
    """The window surface: Glass's true-black panel, with an optional glow.

    set_glow() washes the lower-right corner in a colour (red while something
    is blocked) — faint, so the surface stays black.
    """

    def __init__(self, parent: QWidget | None = None,
                 watermark: QPixmap | None = None) -> None:
        super().__init__(watermark, parent)
        self._glow: QColor | None = None

    def set_glow(self, color: QColor | None) -> None:
        if color != self._glow:
            self._glow = color
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._glow is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, GLASS_RADIUS, GLASS_RADIUS)
        c = self._glow
        low = QRadialGradient(r.width() * 0.92, r.height() * 0.85, r.width() * 0.55)
        low.setColorAt(0.0, QColor(c.red(), c.green(), c.blue(), 26))
        low.setColorAt(1.0, QColor(c.red(), c.green(), c.blue(), 0))
        p.fillPath(path, low)
        p.end()


class GlassCard(QFrame):
    """A flat OLED card: the faint white fill of the Control Center's pills,
    with a thin rim.

    set_tint() washes the card's left edge and rim in a colour (red for a
    blocked device); set_emphasis() brightens the rim (the kernel that boots
    next).
    """

    def __init__(self, radius: int = 14) -> None:
        super().__init__()
        self._radius = radius
        self._tint: QColor | None = None
        self._emph = False
        self._hover = False
        self.setAttribute(Qt.WA_Hover)

    def set_tint(self, color: QColor | None) -> None:
        if color != self._tint:
            self._tint = color
            self.update()

    def set_emphasis(self, on: bool) -> None:
        if on != self._emph:
            self._emph = on
            self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, self._radius, self._radius)
        # PILL_BG (0.06) at rest, PILL_BG_HOVER-ish on hover — same as the
        # Control Center's rows, so the two apps read as one family.
        p.fillPath(path, QColor(255, 255, 255, (24 if self._hover else 15)
                                + (5 if self._emph else 0)))
        tc = self._tint
        if tc is not None:
            t = QLinearGradient(0, 0, r.width(), 0)
            t.setColorAt(0.0, QColor(tc.red(), tc.green(), tc.blue(), 34))
            t.setColorAt(0.6, QColor(tc.red(), tc.green(), tc.blue(), 0))
            p.fillPath(path, t)
            rim = QColor(tc.red(), tc.green(), tc.blue(), 105)
        elif self._emph:
            rim = QColor(255, 255, 255, 115)
        else:
            rim = QColor(255, 255, 255, 34 if self._hover else 20)
        p.setPen(QPen(rim, 1))
        p.drawPath(path)
        p.end()


class IconTile(QWidget):
    """A rounded tile holding one white line-art icon.

    tint: colours the tile (red = blocked); dim: quieter (absent / not
    installed); slash: a red line cut cleanly through the icon (the icon is
    erased under it, so it reads on any background); dot: a small status
    dot on the tile's corner (green = running).
    """

    def __init__(self, icon_path: str, size: int) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self._path = icon_path
        self._tint: QColor | None = None
        self._dim = False
        self._slash = False
        self._dot: QColor | None = None

    def set_state(self, tint: QColor | None = None, dim: bool = False,
                  slash: bool = False, dot: QColor | None = None) -> None:
        new = (tint, dim, slash, dot)
        if new != (self._tint, self._dim, self._slash, self._dot):
            self._tint, self._dim, self._slash, self._dot = new
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        inset = 3.0 if self._dot is not None else 0.5
        r = QRectF(self.rect()).adjusted(0.5, inset, -inset, -0.5)
        rad = r.width() * 0.28
        path = QPainterPath()
        path.addRoundedRect(r, rad, rad)
        tc = self._tint
        if tc is not None:
            fill = QColor(tc.red(), tc.green(), tc.blue(), 42)
            rim = QColor(tc.red(), tc.green(), tc.blue(), 130)
        else:
            fill = QColor(255, 255, 255, 9 if self._dim else 18)
            rim = QColor(255, 255, 255, 16 if self._dim else 34)
        p.fillPath(path, fill)
        p.setPen(QPen(rim, 1))
        p.drawPath(path)

        dpr = self.devicePixelRatioF()
        s = int(r.width() * 0.5)
        color = (QColor(255, 235, 235) if tc is not None
                 else QColor(255, 255, 255, 110 if self._dim else 255))
        icon = svg_pixmap(self._path, s, dpr, color)
        if self._slash:
            q = QPainter(icon)
            q.setRenderHint(QPainter.Antialiasing)
            q.setCompositionMode(QPainter.CompositionMode_Clear)
            q.setPen(QPen(Qt.transparent, 5.5, Qt.SolidLine, Qt.RoundCap))
            q.drawLine(QPointF(0, 0), QPointF(s, s))
            q.end()
        x = r.center().x() - s / 2
        y = r.center().y() - s / 2
        p.drawPixmap(QPointF(x, y), icon)
        if self._slash:
            p.setPen(QPen(_RED.lighter(115), 2.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x + 0.5, y + 0.5), QPointF(x + s - 0.5, y + s - 0.5))
        if self._dot is not None:
            d = 12.0
            c = QRectF(self.width() - d - 0.5, 0.5, d, d)
            p.setPen(QPen(QColor(0, 0, 0), 2.5))   # cut out of the black surface
            p.setBrush(self._dot)
            p.drawEllipse(c)
        p.end()


class Chip(QLabel):
    """A small status pill: coloured dot + text on a tinted pill.
    dot=False gives a plain neutral tag."""

    def __init__(self) -> None:
        super().__init__()
        self.setFont(font(8.5, QFont.DemiBold))
        self.setTextFormat(Qt.RichText)
        # Qt drops border-radius above half the height — pin the height.
        self.setFixedHeight(22)

    def set(self, text: str, color: QColor, dot: bool = True) -> None:
        c = color
        body = (f"<span style='color:{c.name()}'>●</span>&nbsp;&nbsp;{text}"
                if dot else text)
        self.setText(body)
        self.setStyleSheet(
            f"QLabel {{ color: {c.lighter(125).name() if dot else c.name()};"
            f" background: rgba({c.red()},{c.green()},{c.blue()},"
            f"{0.14 if dot else 0.07});"
            f" border: 1px solid rgba({c.red()},{c.green()},{c.blue()},"
            f"{0.30 if dot else 0.14});"
            " border-radius: 10px; padding: 0 10px 0 8px; }")


def chip(text: str, color: QColor | str, dot: bool = True) -> Chip:
    c = Chip()
    c.set(text, QColor(color), dot)
    return c


class CloseButton(QPushButton):
    """The ✕ of the Control Center and Welcome: bare until hovered, then a
    red disc."""

    def __init__(self, size: int = 30) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tr("Close"))

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        hover = self.underMouse()
        if hover:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(224, 68, 68, 64))
            p.drawEllipse(r)
        p.setPen(QPen(QColor(TEXT if hover else DIM), 1.6, Qt.SolidLine, Qt.RoundCap))
        c, k = r.center(), r.width() * 0.17
        p.drawLine(QPointF(c.x() - k, c.y() - k), QPointF(c.x() + k, c.y() + k))
        p.drawLine(QPointF(c.x() + k, c.y() - k), QPointF(c.x() - k, c.y() + k))
        p.end()


def pill_button(text: str, kind: str = "ghost", icon: QPixmap | None = None) -> QPushButton:
    """The Control Center's buttons: 'primary' (solid white), 'ghost' (faint
    white) or 'danger' (red)."""
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(40 if kind == "primary" else 36)
    btn.setFont(font(10, QFont.Bold if kind == "primary" else QFont.Medium))
    if icon is not None and not icon.isNull():
        btn.setIcon(QIcon(icon))
        btn.setIconSize(QSize(16, 16))
    if kind == "primary":
        css = (f"QPushButton {{ color: #0a0a0c; background: {ACCENT}; border: none;"
               " border-radius: 12px; padding: 0 20px; }"
               f"QPushButton:hover {{ background: {ACCENT_HOVER}; }}"
               "QPushButton:pressed { background: #d6d7dc; }"
               f"QPushButton:disabled {{ color: {FAINT}; background: {PILL_BG}; }}")
    elif kind == "danger":
        css = (f"QPushButton {{ color: {BAD_RED}; background: rgba(224,102,102,0.10);"
               " border: none; border-radius: 12px; padding: 0 16px; }"
               "QPushButton:hover { color: #ffffff; background: rgba(224,68,68,0.30); }"
               f"QPushButton:disabled {{ color: {UNK_GRAY}; background: rgba(255,255,255,0.03); }}")
    else:
        css = (f"QPushButton {{ color: {TEXT}; background: rgba(255,255,255,0.08);"
               " border: none; border-radius: 12px; padding: 0 16px; }"
               "QPushButton:hover { background: rgba(255,255,255,0.16); }"
               f"QPushButton:disabled {{ color: {FAINT}; background: rgba(255,255,255,0.04); }}")
    btn.setStyleSheet(css)
    return btn


def app_header(icon_path: str, eyebrow: str, title: str, on_language,
               on_close, dpr: float) -> QHBoxLayout:
    """Icon tile, small-caps eyebrow + title, EN|TR toggle, close."""
    bar = QHBoxLayout()
    bar.setSpacing(0)
    tile = GlassCard(radius=13)
    tile.setFixedSize(46, 46)
    tl = QHBoxLayout(tile)
    tl.setContentsMargins(0, 0, 0, 0)
    ic = QLabel()
    ic.setStyleSheet("background: transparent;")
    ic.setPixmap(svg_pixmap(icon_path, 24, dpr))
    tl.addWidget(ic, 0, Qt.AlignCenter)
    bar.addWidget(tile, 0, Qt.AlignVCenter)
    bar.addSpacing(14)
    titles = QVBoxLayout()
    titles.setSpacing(2)
    titles.addWidget(label(eyebrow, 7.5, FAINT, QFont.Bold, 1.6))
    titles.addWidget(label(title, 17, TEXT, QFont.Bold))
    bar.addLayout(titles)
    bar.addStretch(1)
    bar.addWidget(language_toggle(on_language), 0, Qt.AlignVCenter)
    bar.addSpacing(12)
    close = CloseButton(30)
    close.clicked.connect(on_close)
    bar.addWidget(close, 0, Qt.AlignVCenter)
    return bar


def section_label(text: str, right: QLabel | None = None) -> QHBoxLayout:
    """A small-caps section heading, optionally with a counter on the right."""
    sec = QHBoxLayout()
    sec.setContentsMargins(6, 0, 6, 0)
    sec.addWidget(label(caps(text), 8, FAINT, QFont.Bold, 1.2))
    sec.addStretch(1)
    if right is not None:
        sec.addWidget(right)
    return sec
