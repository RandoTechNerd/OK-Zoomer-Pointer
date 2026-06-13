import sys
import ctypes
from ctypes import wintypes
import traceback
import os
import time
import winreg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QPushButton, QColorDialog,
                             QSystemTrayIcon, QMenu, QFrame, QCheckBox, QRadioButton,
                             QButtonGroup, QScrollArea, QTabWidget)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QPointF, QRect, QRectF, QSettings, QSharedMemory, QUrl, QProcess)
from PyQt6.QtGui import (QPainter, QBrush, QPen, QColor, QPixmap, QImage,
                         QPainterPath, QCursor, QAction, QIcon, QGuiApplication, QDesktopServices)

# ==========================================
# 1. CONSTANTS
# ==========================================
APP_NAME = "OK Zoomer Live"
APP_ID = "RandoTechNerd.OKZoomer.Live.V4"
LOG_FILE = "OK_ZOOMER_LOG.txt"
VERSION = "v4.0"

VK_ALT, VK_SHIFT, VK_MBUTTON = 0x12, 0x10, 0x04
VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT = 0x26, 0x28, 0x25, 0x27
VK_COMMA, VK_PERIOD, VK_C, VK_SLASH, VK_CONTROL = 0xBC, 0xBE, 0x43, 0xBF, 0x11
VK_0, VK_1, VK_2, VK_3, VK_4, VK_8 = 0x30, 0x31, 0x32, 0x33, 0x34, 0x38
VK_NUM0, VK_NUM1, VK_NUM2, VK_NUM3, VK_NUM4, VK_NUM8 = 0x60, 0x61, 0x62, 0x63, 0x64, 0x68

STYLE_NORMAL, STYLE_HIDDEN, STYLE_LASER, STYLE_CROSSHAIR = 0, 1, 2, 3
CAP_STEALTH, CAP_PRESENTATION, CAP_LIVE = 0, 1, 2
SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_RECTANGLE = 0, 1, 2

RAINBOW_COLORS = ["#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0000FF", "#4B0082", "#9400D3", "#FFC0CB", "#39FF14"]

GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

def log_msg(msg):
    try:
        with open(LOG_FILE, "a") as f: f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except: pass

def is_key_pressed(vk):
    try: return bool(GetAsyncKeyState(int(vk)) & 0x8000)
    except: return False

def set_dpi_aware():
    try: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except:
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except:
            try: ctypes.windll.user32.SetProcessDPIAware()
            except: pass

def restore_cursors(): ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)

def create_blank_cursor():
    and_mask = (ctypes.c_ubyte * 128)(*(0xFF for _ in range(128)))
    xor_mask = (ctypes.c_ubyte * 128)(*(0x00 for _ in range(128)))
    return ctypes.windll.user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)

def get_magnifier_icon():
    pix = QPixmap(256, 256); pix.fill(Qt.GlobalColor.transparent); p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Draw Handle
    p.setPen(QPen(QColor("#2c3e50"), 20, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(160, 160, 230, 230)
    # Draw Lens
    p.setPen(QPen(QColor("#3498db"), 15))
    p.setBrush(QBrush(QColor(255, 255, 255, 40)))
    p.drawEllipse(30, 30, 150, 150)
    # Draw Shine
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(QColor(255, 255, 255, 80)))
    p.drawEllipse(60, 60, 40, 20)
    p.end(); return QIcon(pix)

# ==========================================
# 1b. LIVE MAGNIFIER (Windows Magnification API)
# ==========================================
# Unlike snapshot Presentation mode, this updates every frame (no freeze on video) and the OS
# automatically excludes the magnifier's own window from the captured source, so there is no
# hall-of-mirrors recursion even though OBS/Zoom can see the lens normally.
_LRESULT = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
_WNDPROCTYPE = ctypes.WINFUNCTYPE(_LRESULT, wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM)

class WNDCLASSEX(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("style", ctypes.c_uint), ("lpfnWndProc", _WNDPROCTYPE),
                ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON), ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

class MAGTRANSFORM(ctypes.Structure):
    _fields_ = [("v", ctypes.c_float * 9)]

class WinLiveMagnifier:
    _CLASS_NAME = "OKZoomerLiveHostClass"

    def __init__(self):
        self.hwnd_host = None; self.hwnd_mag = None; self._wndproc = None
        self._class_atom = None; self._ok = False; self._last_dw = None; self._last_dh = None; self._last_circle = None; self._last_zoom = None

    def _setup(self):
        self.u32 = ctypes.windll.user32; self.g32 = ctypes.windll.gdi32
        self.k32 = ctypes.windll.kernel32; self.mag = ctypes.windll.Magnification
        u, g, k, m = self.u32, self.g32, self.k32, self.mag
        u.CreateWindowExW.restype = wintypes.HWND
        u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HMENU,
            wintypes.HINSTANCE, wintypes.LPVOID]
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        u.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HANDLE, wintypes.BOOL]
        u.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_ubyte, wintypes.DWORD]
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.RegisterClassExW.restype = wintypes.ATOM; u.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEX)]
        u.DefWindowProcW.restype = _LRESULT
        u.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
        g.CreateEllipticRgn.restype = wintypes.HANDLE; g.CreateRectRgn.restype = wintypes.HANDLE
        k.GetModuleHandleW.restype = wintypes.HMODULE
        m.MagInitialize.restype = wintypes.BOOL
        m.MagSetWindowSource.argtypes = [wintypes.HWND, wintypes.RECT]; m.MagSetWindowSource.restype = wintypes.BOOL
        m.MagSetWindowTransform.argtypes = [wintypes.HWND, ctypes.POINTER(MAGTRANSFORM)]; m.MagSetWindowTransform.restype = wintypes.BOOL

    def create(self):
        if self._ok and self.hwnd_host: return True
        try:
            self._setup()
            if not self.mag.MagInitialize(): log_msg("LIVE: MagInitialize failed (needs Win10 2004+)"); return False
            hInst = self.k32.GetModuleHandleW(None)
            if self._class_atom is None:
                self._wndproc = _WNDPROCTYPE(lambda h, msg, wp, lp: self.u32.DefWindowProcW(h, msg, wp, lp))
                wc = WNDCLASSEX(); wc.cbSize = ctypes.sizeof(WNDCLASSEX); wc.style = 0
                wc.lpfnWndProc = self._wndproc; wc.hInstance = hInst; wc.lpszClassName = self._CLASS_NAME
                self._class_atom = self.u32.RegisterClassExW(ctypes.byref(wc))
            WS_POPUP = 0x80000000; WS_CLIPCHILDREN = 0x02000000; WS_VISIBLE = 0x10000000; WS_CHILD = 0x40000000
            EX = 0x00000008 | 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000  # TOPMOST|LAYERED|TRANSPARENT|TOOLWINDOW|NOACTIVATE
            self.hwnd_host = self.u32.CreateWindowExW(EX, self._CLASS_NAME, "OKZoomerLive",
                WS_POPUP | WS_CLIPCHILDREN, 0, 0, 400, 400, None, None, hInst, None)
            if not self.hwnd_host: log_msg("LIVE: host create failed"); return False
            self.u32.SetLayeredWindowAttributes(self.hwnd_host, 0, 255, 0x00000002)  # LWA_ALPHA, opaque
            # No MS_SHOWMAGNIFIEDCURSOR: the real OS cursor (hardware, lag-free) stays the only pointer.
            self.hwnd_mag = self.u32.CreateWindowExW(0, "Magnifier", "OKZoomerMagChild",
                WS_CHILD | WS_VISIBLE, 0, 0, 400, 400, self.hwnd_host, None, hInst, None)
            if not self.hwnd_mag: log_msg("LIVE: magnifier child create failed"); return False
            self._ok = True; return True
        except Exception as e:
            log_msg(f"LIVE create error: {e}\n{traceback.format_exc()}"); return False

    def update(self, cx, cy, dw, dh, zoom, circle=True):
        if not self._ok: return
        try:
            dw = max(20, int(dw)); dh = max(20, int(dh)); hw = dw // 2; hh = dh // 2; zoom = max(1.1, float(zoom))
            SWP_NOACTIVATE = 0x0010; SWP_NOZORDER = 0x0004; SWP_NOSIZE = 0x0001
            resized = (dw != self._last_dw or dh != self._last_dh or circle != self._last_circle)
            # Move the host every frame; only resize host+child+region when the size actually changes.
            # hWndInsertAfter is ignored under SWP_NOZORDER, so z-order isn't recomputed each frame (= smooth).
            flags = SWP_NOACTIVATE | SWP_NOZORDER | (0 if resized else SWP_NOSIZE)
            self.u32.SetWindowPos(self.hwnd_host, wintypes.HWND(0), cx - hw, cy - hh, dw, dh, flags)
            if resized:
                self.u32.SetWindowPos(self.hwnd_mag, wintypes.HWND(0), 0, 0, dw, dh, SWP_NOACTIVATE | SWP_NOZORDER)
                rgn = self.g32.CreateEllipticRgn(0, 0, dw, dh) if circle else self.g32.CreateRectRgn(0, 0, dw, dh)
                self.u32.SetWindowRgn(self.hwnd_host, rgn, True)  # window takes ownership of rgn
                self._last_dw = dw; self._last_dh = dh; self._last_circle = circle
            if zoom != self._last_zoom:
                t = MAGTRANSFORM(); t.v[0] = zoom; t.v[4] = zoom; t.v[8] = 1.0
                self.mag.MagSetWindowTransform(self.hwnd_mag, ctypes.byref(t)); self._last_zoom = zoom
            sw = max(1, int(dw / zoom)); sh = max(1, int(dh / zoom))
            self.mag.MagSetWindowSource(self.hwnd_mag, wintypes.RECT(cx - sw // 2, cy - sh // 2, cx - sw // 2 + sw, cy - sh // 2 + sh))
        except Exception as e:
            log_msg(f"LIVE update error: {e}")

    def cursor_phys(self):
        pt = wintypes.POINT(); self.u32.GetCursorPos(ctypes.byref(pt)); return pt.x, pt.y
    def show(self):
        if not self._ok: return
        self.u32.ShowWindow(self.hwnd_host, 8)  # SW_SHOWNA (no focus steal)
        # Raise to topmost once here; per-frame moves then skip z-order work for smoothness.
        SWP_NOMOVE = 0x0002; SWP_NOSIZE = 0x0001; SWP_NOACTIVATE = 0x0010
        self.u32.SetWindowPos(self.hwnd_host, wintypes.HWND(-1), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    def hide(self):
        if self._ok: self.u32.ShowWindow(self.hwnd_host, 0)  # SW_HIDE
    def destroy(self):
        try:
            if self.hwnd_host: self.u32.DestroyWindow(self.hwnd_host)
            self.mag.MagUninitialize()
        except: pass
        self.hwnd_host = self.hwnd_mag = None; self._ok = False

class SettingsWindow(QWidget):
    def __init__(self, magnifier):
        super().__init__()
        self.magnifier = magnifier; self.setWindowTitle(f"{APP_NAME} Settings"); self.setWindowIcon(get_magnifier_icon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        root = QVBoxLayout(self); root.setContentsMargins(12, 12, 12, 12); root.setSpacing(10)

        # --- Header (logo + title) ---
        header = QHBoxLayout(); logo = QLabel(); logo.setPixmap(get_magnifier_icon().pixmap(48, 48)); header.addWidget(logo)
        vbox = QVBoxLayout(); vbox.setSpacing(0)
        vbox.addWidget(QLabel("<span style='font-size:19px; font-weight:bold; color:#2c3e50;'>OK Zoomer</span>"
                              "&nbsp;<span style='font-size:12px; font-weight:bold; color:#2980b9; letter-spacing:2px;'>LIVE</span>"))
        vbox.addWidget(QLabel(f"<span style='color:#7f8c8d;'>{VERSION}</span>"))
        header.addLayout(vbox); header.addStretch(); root.addLayout(header)

        # --- Tabs ---
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)

        # Appearance tab
        ap = self._tab("Appearance")
        ap.addWidget(self._hdr("Magnifier Shape"))
        hl = QHBoxLayout(); self.shape_group = QButtonGroup(self)
        for label, sid in [("Circle", SHAPE_CIRCLE), ("Square", SHAPE_SQUARE), ("Rectangle", SHAPE_RECTANGLE)]:
            rb = QRadioButton(label); self.shape_group.addButton(rb, sid); rb.clicked.connect(self.update_shape); hl.addWidget(rb)
        ap.addLayout(hl)
        ap.addWidget(self._hdr("Pointer Style"))
        sl = QHBoxLayout(); self.style_group = QButtonGroup(self)
        for label, sid in [("Normal", STYLE_NORMAL), ("Hidden", STYLE_HIDDEN), ("Laser", STYLE_LASER), ("Crosshair", STYLE_CROSSHAIR)]:
            rb = QRadioButton(label); self.style_group.addButton(rb, sid); rb.clicked.connect(self.update_style); sl.addWidget(rb)
        ap.addLayout(sl)
        ap.addWidget(self._hdr("Default Zoom"))
        self.zoom_s = QSlider(Qt.Orientation.Horizontal); self.zoom_s.setRange(11, 150); self.zoom_s.valueChanged.connect(self.update_zoom); ap.addWidget(self.zoom_s)
        ap.addWidget(self._hdr("Magnifier Size"))
        self.radius_s = QSlider(Qt.Orientation.Horizontal); self.radius_s.setRange(50, 600); self.radius_s.setValue(self.magnifier.radius); self.radius_s.valueChanged.connect(self.update_radius); ap.addWidget(self.radius_s)
        self.fps_l = QLabel("Live Smoothness:"); ap.addWidget(self.fps_l)
        self.fps_s = QSlider(Qt.Orientation.Horizontal); self.fps_s.setRange(30, 144); self.fps_s.valueChanged.connect(self.update_fps); ap.addWidget(self.fps_s)
        ap.addStretch()

        # Capture tab
        cp = self._tab("Capture")
        info = QLabel("Hold your activation key to zoom. <b>Live</b> is smoothest for video; "
                      "<b>Presentation</b> is a frozen snapshot; <b>Stealth</b> hides from recording. "
                      "Screen size &amp; scaling are auto-detected.")
        info.setWordWrap(True); info.setStyleSheet("color:#555;"); cp.addWidget(info)
        cp.addWidget(self._hdr("Capture Mode")); self.cap_group = QButtonGroup(self)
        r1 = QRadioButton("STEALTH  (invisible to recording)"); self.cap_group.addButton(r1, CAP_STEALTH); cp.addWidget(r1)
        r2 = QRadioButton("PRESENTATION  (snapshot — visible to OBS, freezes video)"); r2.setStyleSheet("font-weight:bold; color:#27ae60;"); self.cap_group.addButton(r2, CAP_PRESENTATION); cp.addWidget(r2)
        r3 = QRadioButton("LIVE  (smooth — best for video/animation, visible to OBS)"); r3.setStyleSheet("font-weight:bold; color:#2980b9;"); self.cap_group.addButton(r3, CAP_LIVE); cp.addWidget(r3)
        r1.clicked.connect(self.update_capture); r2.clicked.connect(self.update_capture); r3.clicked.connect(self.update_capture)
        cp.addStretch()

        # Controls tab
        ct = self._tab("Controls")
        ct.addWidget(self._hdr("Activation Keys"))
        ct.addWidget(QLabel("Hold any selected key (or middle mouse) to zoom."))
        kl = QHBoxLayout(); self.alt_cb = QPushButton("Alt"); self.shift_cb = QPushButton("Shift"); self.mid_cb = QPushButton("Mid-Mouse")
        for cb in [self.alt_cb, self.shift_cb, self.mid_cb]: cb.setCheckable(True); cb.clicked.connect(self.update_keys); kl.addWidget(cb)
        ct.addLayout(kl)
        hint = QLabel("While zooming (hold a keypad number): <b>0</b> pointer · <b>1</b> border · <b>2</b> rainbow · "
                      "<b>4</b> shape · <b>8</b> spotlight · <b>arrows</b> zoom/size.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#777; margin-top:6px;"); ct.addWidget(hint)
        ct.addStretch()

        # Calibration tab
        cb = self._tab("Calibration")
        cb.addWidget(QLabel("Auto-detect handles scaling. Only touch these if the zoom looks misaligned."))
        cb.addWidget(self._hdr("Zoom Trim (1.0 = Auto)"))
        self.dpi_s = QSlider(Qt.Orientation.Horizontal); self.dpi_s.setRange(5, 20); self.dpi_s.valueChanged.connect(self.update_dpi); cb.addWidget(self.dpi_s)
        self.dpi_l = QLabel(""); cb.addWidget(self.dpi_l)
        cb.addWidget(self._hdr("Horizontal Fine-Tune"))
        self.offx_s = QSlider(Qt.Orientation.Horizontal); self.offx_s.setRange(-200, 200); self.offx_s.valueChanged.connect(self.update_offset_x); cb.addWidget(self.offx_s)
        cb.addWidget(self._hdr("Vertical Fine-Tune"))
        self.offy_s = QSlider(Qt.Orientation.Horizontal); self.offy_s.setRange(-200, 200); self.offy_s.valueChanged.connect(self.update_offset_y); cb.addWidget(self.offy_s)
        self.reset_cal_btn = QPushButton("↺ Reset to Auto (Recommended)"); self.reset_cal_btn.setStyleSheet("background-color:#3498db; color:white; font-weight:bold; padding:6px;"); self.reset_cal_btn.clicked.connect(self.reset_calibration); cb.addWidget(self.reset_cal_btn)
        cb.addStretch()

        # --- Footer buttons ---
        self.apply_btn = QPushButton("Save & Close"); self.apply_btn.clicked.connect(self.hide); self.apply_btn.setStyleSheet("background-color:#2c3e50; color:white; font-weight:bold; padding:9px;"); root.addWidget(self.apply_btn)
        self.restart_btn = QPushButton("♻ Restart App"); self.restart_btn.setStyleSheet("background-color:#e67e22; color:white; font-weight:bold; padding:6px;"); self.restart_btn.clicked.connect(self.magnifier.restart_app); root.addWidget(self.restart_btn)

        self.setMinimumSize(360, 420); self._restore_geometry(); self.refresh_ui()

    def _tab(self, title):
        """Create a scrollable tab and return its content layout (so it works at any window size)."""
        content = QWidget(); lay = QVBoxLayout(content); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(8)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.Shape.NoFrame); sa.setWidget(content)
        self.tabs.addTab(sa, title); return lay

    def _hdr(self, text):
        l = QLabel(f"<b>{text}</b>"); l.setStyleSheet("color:#2c3e50; margin-top:6px;"); return l

    def _restore_geometry(self):
        geo = self.magnifier.settings_manager.value("settings_geometry")
        if geo is not None:
            try: self.restoreGeometry(geo); return
            except: pass
        avail = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(min(480, avail.width()), min(620, int(avail.height() * 0.9)))

    def _save_geometry(self):
        try: self.magnifier.settings_manager.setValue("settings_geometry", self.saveGeometry())
        except: pass
    def hideEvent(self, e): self._save_geometry(); super().hideEvent(e)
    def closeEvent(self, e): self._save_geometry(); super().closeEvent(e)
    def refresh_ui(self):
        self.alt_cb.setChecked(VK_ALT in self.magnifier.activation_keys); self.shift_cb.setChecked(VK_SHIFT in self.magnifier.activation_keys); self.mid_cb.setChecked(VK_MBUTTON in self.magnifier.activation_keys)
        if self.shape_group.button(self.magnifier.shape): self.shape_group.button(self.magnifier.shape).setChecked(True)
        if self.style_group.button(self.magnifier.pointer_style): self.style_group.button(self.magnifier.pointer_style).setChecked(True)
        if self.cap_group.button(self.magnifier.capture_mode): self.cap_group.button(self.magnifier.capture_mode).setChecked(True)
        self.zoom_s.setValue(int(self.magnifier.zoom * 10)); self.radius_s.setValue(self.magnifier.radius)
        self.offx_s.setValue(self.magnifier.pull_x); self.offy_s.setValue(self.magnifier.pull_y)
        self.dpi_s.setValue(int(self.magnifier.dpi_trim * 10)); self.dpi_l.setText(f"Trim: {self.magnifier.dpi_trim}x (1.0 = Auto)")
        self.fps_s.setValue(self.magnifier.live_fps); self.fps_l.setText(f"Live Smoothness: {self.magnifier.live_fps} FPS (higher = smoother, more CPU)")
    def update_dpi(self, v): self.magnifier.dpi_trim = v / 10.0; self.dpi_l.setText(f"Trim: {self.magnifier.dpi_trim}x (1.0 = Auto)"); self.magnifier.save_settings()
    def update_fps(self, v):
        self.magnifier.live_fps = v; self.fps_l.setText(f"Live Smoothness: {v} FPS (higher = smoother, more CPU)")
        self.magnifier.apply_timer_rate(); self.magnifier.save_settings()
    def update_keys(self):
        keys = []; [keys.append(k) for k, b in [(VK_ALT, self.alt_cb.isChecked()), (VK_SHIFT, self.shift_cb.isChecked()), (VK_MBUTTON, self.mid_cb.isChecked())] if b]
        if not keys: self.alt_cb.setChecked(True); keys = [VK_ALT]
        self.magnifier.activation_keys = keys; self.magnifier.save_settings(); self.refresh_ui()
    def update_capture(self, v): self.magnifier.capture_mode = self.cap_group.checkedId(); self.magnifier.save_settings(); self.magnifier.apply_capture_flags()
    def update_offset_x(self, v): self.magnifier.pull_x = v; self.magnifier.save_settings()
    def update_offset_y(self, v): self.magnifier.pull_y = v; self.magnifier.save_settings()
    def reset_calibration(self):
        # One-click return to pure auto-detect: no manual offsets, no zoom trim.
        self.magnifier.pull_x = 0; self.magnifier.pull_y = 0; self.magnifier.dpi_trim = 1.0
        self.magnifier.save_settings(); self.refresh_ui()
    def update_shape(self, v): self.magnifier.shape = self.shape_group.checkedId(); self.magnifier.save_settings(); self.magnifier.update_window_size()
    def update_style(self, v): self.magnifier.pointer_style = self.style_group.checkedId(); self.magnifier.save_settings(); self.magnifier.force_cursor_update()
    def update_zoom(self, v): self.magnifier.zoom = v / 10.0; self.magnifier.save_settings()
    def update_radius(self, v): self.magnifier.radius = v; self.magnifier.update_window_size(); self.magnifier.save_settings()
    def pick_color(self):
        c = QColorDialog.getColor(self.magnifier.border_color, self, "Pick Color"); [self.magnifier.__setattr__('border_color', c), self.magnifier.save_settings(), self.refresh_ui()] if c.isValid() else None
    def set_clear_color(self): self.magnifier.border_color = QColor(0,0,0,0) if self.clear_btn.isChecked() else QColor("#00FF00"); self.magnifier.save_settings(); self.refresh_ui()

class Magnifier(QWidget):
    def __init__(self):
        super().__init__()
        try:
            self._cursor_hidden = False; self.settings_manager = QSettings("RTN", "OK_Zoomer_Supreme_V3"); self.tick_rate = 16
            self.pix = None; self._is_active = False; self._grab_pos = QPoint(0, 0); self.spotlight_enabled = False
            self._frac = (0.0, 0.0, 1.0, 1.0)  # (x, y, w, h) fraction of lens that self.pix maps to (anti-edge-bend)
            self.live = WinLiveMagnifier(); self._live_active = False; self._use_cache = False
            self._last_0, self._last_1, self._last_2, self._last_3, self._last_4, self._last_8 = False, False, False, False, False, False
            self.load_settings(); self._cache = None
            
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            
            self.update_window_size(); self.apply_capture_flags()
            self.tray_dummy = QWidget(); self.tray = QSystemTrayIcon(self.tray_dummy); self.update_tray(False)
            self.menu = QMenu(self.tray_dummy); self.menu.addAction("Settings", self.show_settings); self.menu.addAction("Exit", self.emergency_exit); self.tray.setContextMenu(self.menu); self.tray.show()
            self.timer = QTimer(); self.timer.setTimerType(Qt.TimerType.PreciseTimer)  # steady ticks = smoother follow
            self.timer.timeout.connect(self.tick); self.timer.start(self.tick_rate)
            self.settings_window = SettingsWindow(self); self.hide(); QTimer.singleShot(1000, self.show_settings)
            log_msg(f"{VERSION} Started.")
        except Exception as e: log_msg(f"INIT ERROR: {e}\n{traceback.format_exc()}")

    def load_settings(self):
        self.zoom = float(self.settings_manager.value("zoom", 2.0)); self.radius = int(self.settings_manager.value("radius", 150))
        self.border_color = QColor(self.settings_manager.value("color", "#00FF00"))
        self.pointer_style = int(self.settings_manager.value("pointer_style", STYLE_NORMAL)); self.shape = int(self.settings_manager.value("shape", SHAPE_CIRCLE))
        self.capture_mode = int(self.settings_manager.value("capture_mode", CAP_PRESENTATION))
        # QSettings stores negatives as unsigned DWORDs on Windows; restore the sign and clamp to the slider range.
        def _signed(key):
            try: v = int(self.settings_manager.value(key, 0))
            except: return 0
            if v >= 0x80000000: v -= 0x100000000   # unsigned 32-bit -> signed
            return max(-200, min(200, v))
        self.pull_x = _signed("pull_x"); self.pull_y = _signed("pull_y")
        self.dpi_trim = float(self.settings_manager.value("dpi_trim", 1.0))  # 1.0 = pure auto-detect; optional manual nudge
        self.live_fps = max(30, min(144, int(self.settings_manager.value("live_fps", 60))))  # Live mode update rate
        self.color_cycle_idx = 0; keys = self.settings_manager.value("activation_keys", [VK_ALT, VK_MBUTTON])
        try: self.activation_keys = [int(k) for k in (keys if isinstance(keys, list) else [keys])]
        except: self.activation_keys = [VK_ALT, VK_MBUTTON]

    def save_settings(self):
        self.settings_manager.setValue("zoom", self.zoom); self.settings_manager.setValue("radius", self.radius); self.settings_manager.setValue("color", self.border_color.name(QColor.NameFormat.HexArgb))
        self.settings_manager.setValue("pointer_style", self.pointer_style); self.settings_manager.setValue("shape", self.shape); self.settings_manager.setValue("activation_keys", self.activation_keys)
        self.settings_manager.setValue("capture_mode", self.capture_mode); self.settings_manager.setValue("pull_x", self.pull_x); self.settings_manager.setValue("pull_y", self.pull_y); self.settings_manager.setValue("dpi_trim", self.dpi_trim); self.settings_manager.setValue("live_fps", self.live_fps)

    def update_window_size(self):
        self.setMinimumSize(0, 0); self.setMaximumSize(16777215, 16777215)
        if self.spotlight_enabled: 
            u32 = ctypes.windll.user32; self.setGeometry(u32.GetSystemMetrics(76), u32.GetSystemMetrics(77), u32.GetSystemMetrics(78), u32.GetSystemMetrics(79))
        else:
            w, h = int(self.radius * 2 + 100), int(self.radius * 2 + 100); w = int(w * 1.5) if self.shape == SHAPE_RECTANGLE else w; self.setFixedSize(w, h)
        self.setWindowOpacity(1.0)

    def apply_timer_rate(self):
        # Live mode runs at the user-chosen FPS; other modes stay at the lighter base rate.
        try:
            interval = max(1, int(1000 / self.live_fps)) if self._live_active else self.tick_rate
            if self.timer.interval() != interval: self.timer.setInterval(interval)
        except: pass

    def apply_capture_flags(self):
        try:
            hwnd = int(self.winId())
            # Only STEALTH hides from screen capture; PRESENTATION & LIVE stay visible to OBS.
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011 if self.capture_mode == CAP_STEALTH else 0x00000000)
        except: pass
        # If we left LIVE mode, make sure the native live window is hidden.
        if self.capture_mode != CAP_LIVE: self.live.hide()

    def update_tray(self, active):
        pix = QPixmap(32, 32); pix.fill(Qt.GlobalColor.transparent); p = QPainter(pix)
        p.setBrush(QBrush(QColor("#2ecc71") if active else QColor("#e74c3c"))); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(4, 4, 24, 24); p.end(); self.tray.setIcon(QIcon(pix))

    def show_settings(self): self.settings_window.refresh_ui(); self.settings_window.show(); self.settings_window.raise_(); self.settings_window.activateWindow()
    def force_cursor_update(self):
        if self._is_active: self.toggle_global_cursor(self.pointer_style != STYLE_NORMAL)
    def toggle_global_cursor(self, hide):
        try:
            if hide and not self._cursor_hidden:
                blank = create_blank_cursor(); [ctypes.windll.user32.SetSystemCursor(ctypes.windll.user32.CopyImage(blank, 2, 0, 0, 0), cid) for cid in [32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644, 32645, 32646, 32648, 32649, 32511]]; self._cursor_hidden = True
            elif not hide and self._cursor_hidden: restore_cursors(); self._cursor_hidden = False
        except: pass

    def emergency_exit(self): self.live.destroy(); restore_cursors(); QApplication.instance().quit()
    def restart_app(self): self.live.destroy(); restore_cursors(); QProcess.startDetached(sys.executable, [os.path.abspath(__file__)]); QApplication.instance().quit()

    def tick(self):
        try:
            is_down = any(is_key_pressed(int(key)) for key in self.activation_keys)
            
            if is_down and not self._is_active:
                self._is_active = True; self.update_tray(True)
                # LIVE mode uses the native Magnification window; fall back to snapshot if it can't start.
                self._live_active = (self.capture_mode == CAP_LIVE and self.live.create())
                if self._live_active:
                    self.live.show(); self.apply_timer_rate()
                    # Qt window rides on top as a transparent overlay drawing the border + pointer marker.
                    self.update_window_size(); self.show(); self.raise_()
                    if self.pointer_style != STYLE_NORMAL: self.toggle_global_cursor(True)
                else:
                    self._use_cache = (self.capture_mode != CAP_STEALTH)  # snapshot for PRESENTATION or failed-LIVE
                    if self._use_cache:
                        screen = QGuiApplication.screenAt(QCursor.pos())
                        if not screen: screen = QGuiApplication.primaryScreen()
                        self._cache_rect = screen.geometry(); self._cache = screen.grabWindow(0)
                        # Work in raw device pixels: a DPR-tagged pixmap makes drawPixmap mis-scale
                        # the source rect, shoving the image up-left on scaled (e.g. 150%) displays.
                        self._cache.setDevicePixelRatio(1.0)
                    self.update_window_size(); self.show(); self.raise_()
                    if self.pointer_style != STYLE_NORMAL: self.toggle_global_cursor(True)
            elif not is_down and self._is_active:
                self._is_active = False; self.update_tray(False); self.hide(); self.live.hide()
                self._cache = None; self._live_active = False; self.apply_timer_rate()
                if self.pointer_style != STYLE_NORMAL: self.toggle_global_cursor(False)
            
            if is_down:
                changed = False; k0 = is_key_pressed(VK_0) or is_key_pressed(VK_NUM0)
                if k0 and not self._last_0: self.pointer_style = (self.pointer_style + 1) % 4; changed = True; self.force_cursor_update()
                self._last_0 = k0
                k1 = is_key_pressed(VK_1) or is_key_pressed(VK_NUM1)
                if k1 and not self._last_1: self.border_color = QColor(0,0,0,0) if self.border_color.alpha() != 0 else QColor("#FFFFFF"); changed = True
                self._last_1 = k1
                k2 = is_key_pressed(VK_2) or is_key_pressed(VK_NUM2)
                if k2 and not self._last_2: self.border_color = QColor(RAINBOW_COLORS[self.color_cycle_idx]); self.color_cycle_idx = (self.color_cycle_idx + 1) % len(RAINBOW_COLORS); changed = True
                self._last_2 = k2
                k3 = is_key_pressed(VK_3) or is_key_pressed(VK_NUM3)
                if k3 and not self._last_3: self.border_color = QColor("#000000"); changed = True
                self._last_3 = k3
                k4 = is_key_pressed(VK_4) or is_key_pressed(VK_NUM4)
                if k4 and not self._last_4: self.shape = (self.shape + 1) % 3; changed = True; self.update_window_size()
                self._last_4 = k4
                k8 = is_key_pressed(VK_8) or is_key_pressed(VK_NUM8)
                if k8 and not self._last_8: self.spotlight_enabled = not self.spotlight_enabled; changed = True; self.update_window_size()
                self._last_8 = k8
                if is_key_pressed(VK_UP): self.zoom = min(15.0, self.zoom + 0.05); changed = True
                if is_key_pressed(VK_DOWN): self.zoom = max(1.1, self.zoom - 0.05); changed = True
                if is_key_pressed(VK_RIGHT): self.radius = min(600, self.radius + 3); self.update_window_size(); changed = True
                if is_key_pressed(VK_LEFT): self.radius = max(50, self.radius - 3); self.update_window_size(); changed = True
                if changed: self.save_settings(); self.settings_window.refresh_ui()

            if not is_down: return

            if self._live_active:
                # Live mode: drive the native Magnification window in raw screen pixels (any DPI).
                cx, cy = self.live.cursor_phys()
                scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
                scale = scr.devicePixelRatio() if scr else 1.0
                rw = self.radius * 1.5 if self.shape == SHAPE_RECTANGLE else self.radius
                self.live.update(cx, cy, int(rw * 2 * scale), int(self.radius * 2 * scale), self.zoom, circle=(self.shape == SHAPE_CIRCLE))
                # Just move the transparent overlay each frame; only repaint it when its look changed.
                pos = QCursor.pos(); self.move(int(pos.x() - self.width() / 2.0), int(pos.y() - self.height() / 2.0))
                if changed: self.update()
                return

            pos = QCursor.pos(); self.move(int(pos.x() - self.width() / 2.0), int(pos.y() - self.height() / 2.0))
            rw = int(self.radius * 1.5) if self.shape == SHAPE_RECTANGLE else self.radius
            ocw, och = int((rw * 2) / self.zoom), int((self.radius * 2) / self.zoom)   # logical capture region
            gx, gy = pos.x() - (ocw / 2.0), pos.y() - (och / 2.0)                       # logical top-left (global coords)
            self._frac = (0.0, 0.0, 1.0, 1.0); self.pix = None

            if self._use_cache and self._cache:
                # Auto-detect scale = physical cache pixels per logical pixel. This equals the
                # monitor's display scaling, measured directly, so it works on ANY screen/DPI.
                gw, gh = self._cache_rect.width(), self._cache_rect.height()
                sc_x = (self._cache.width() / gw if gw else 1.0) * self.dpi_trim
                sc_y = (self._cache.height() / gh if gh else 1.0) * self.dpi_trim
                px = (gx - self._cache_rect.x()) * sc_x + self.pull_x
                py = (gy - self._cache_rect.y()) * sc_y + self.pull_y
                pw, ph = ocw * sc_x, och * sc_y
                cw, ch = float(self._cache.width()), float(self._cache.height())
                # Clamp source rect to the cache bounds so we never copy off the edge (= no bending).
                vx0, vy0 = max(0.0, px), max(0.0, py)
                vx1, vy1 = min(cw, px + pw), min(ch, py + ph)
                if vx1 - vx0 >= 1.0 and vy1 - vy0 >= 1.0 and pw > 0 and ph > 0:
                    self.pix = self._cache.copy(int(vx0), int(vy0), int(vx1 - vx0), int(vy1 - vy0))
                    # Where this valid slice sits within the lens (rest stays black).
                    self._frac = ((vx0 - px) / pw, (vy0 - py) / ph, (vx1 - vx0) / pw, (vy1 - vy0) / ph)
            else:
                # Live capture from whichever monitor the cursor is on (multi-monitor safe).
                screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
                if screen and ocw > 0 and och > 0:
                    geo = screen.geometry()
                    vx0, vy0 = max(float(geo.x()), gx), max(float(geo.y()), gy)
                    vx1 = min(float(geo.x() + geo.width()), gx + ocw)
                    vy1 = min(float(geo.y() + geo.height()), gy + och)
                    if vx1 - vx0 >= 1.0 and vy1 - vy0 >= 1.0:
                        self.pix = screen.grabWindow(0, int(vx0), int(vy0), int(vx1 - vx0), int(vy1 - vy0))
                        self.pix.setDevicePixelRatio(1.0)  # keep source-rect math in raw device pixels
                        self._frac = ((vx0 - gx) / ocw, (vy0 - gy) / och, (vx1 - vx0) / ocw, (vy1 - vy0) / och)
            self.update()
        except Exception as e: log_msg(f"TICK ERROR: {e}")

    def paintEvent(self, event):
        if not self._is_active: return
        try:
            if self._live_active:
                # Overlay only: the magnified image comes from the native window beneath; here we
                # paint just the colored border ring + pointer marker over a fully transparent center.
                p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
                center = QPointF(self.width()/2.0, self.height()/2.0)
                rw = self.radius * 1.5 if self.shape == SHAPE_RECTANGLE else float(self.radius); rh = float(self.radius)
                path = QPainterPath()
                if self.shape == SHAPE_CIRCLE: path.addEllipse(center, rw, rh)
                else: path.addRect(center.x() - rw, center.y() - rh, rw * 2, rh * 2)
                if self.border_color.alpha() != 0: p.setPen(QPen(self.border_color, 5)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
                if self.pointer_style == STYLE_LASER: p.setBrush(QBrush(QColor(255, 0, 0, 200))); p.setPen(QPen(QColor(255, 255, 255, 150), 2)); p.drawEllipse(center, 5, 5); p.setPen(QPen(QColor(255, 0, 0, 100), 10)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(center, 8, 8)
                elif self.pointer_style == STYLE_CROSSHAIR: p.setPen(QPen(self.border_color, 2)); l = 20; p.drawLine(center + QPointF(-l, 0), center + QPointF(l, 0)); p.drawLine(center + QPointF(0, -l), center + QPointF(0, l)); p.drawEllipse(center, 10, 10)
                return
            if self.pix is None: return
            p = QPainter(self); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
            center = QPointF(self.width()/2.0, self.height()/2.0); rw, rh = float(self.radius), float(self.radius); rw = rw * 1.5 if self.shape == SHAPE_RECTANGLE else rw; path = QPainterPath()
            if self.shape == SHAPE_CIRCLE: path.addEllipse(center, rw, rh)
            else: path.addRect(center.x() - rw, center.y() - rh, rw * 2, rh * 2)
            if self.spotlight_enabled: p.fillRect(self.rect(), QColor(0, 0, 0, 180)); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear); p.drawPath(path); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setClipPath(path); p.fillRect(self.rect(), QColor(0, 0, 0, 255))
            fx, fy, fw, fh = self._frac; lx, ly, lw, lh = center.x() - rw, center.y() - rh, rw * 2, rh * 2
            p.drawPixmap(QRectF(lx + fx * lw, ly + fy * lh, fw * lw, fh * lh), self.pix, QRectF(0, 0, self.pix.width(), self.pix.height()))
            p.setClipping(False); p.setPen(QPen(self.border_color, 5)); p.drawPath(path)
            if self.pointer_style == STYLE_LASER: p.setBrush(QBrush(QColor(255, 0, 0, 200))); p.setPen(QPen(QColor(255, 255, 255, 150), 2)); p.drawEllipse(center, 5, 5); p.setPen(QPen(QColor(255, 0, 0, 100), 10)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(center, 8, 8)
            elif self.pointer_style == STYLE_CROSSHAIR: p.setPen(QPen(self.border_color, 2)); l = 20; p.drawLine(center + QPointF(-l, 0), center + QPointF(l, 0)); p.drawLine(center + QPointF(0, -l), center + QPointF(0, l)); p.drawEllipse(center, 10, 10)
        except Exception as e: log_msg(f"PAINT ERROR: {e}")

if __name__ == "__main__":
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"): QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    set_dpi_aware(); restore_cursors(); app = QApplication(sys.argv); app.setWindowIcon(get_magnifier_icon())
    # Single-instance guard: if create() fails, another copy is already running -> exit
    # (otherwise multiple magnifiers stack and overlapping lenses flicker/bend at edges).
    shared_mem = QSharedMemory(APP_ID)
    if not shared_mem.create(1):
        log_msg("Another instance is already running. Exiting.")
        sys.exit(0)
    app.setQuitOnLastWindowClosed(False); app.aboutToQuit.connect(restore_cursors)
    try: m = Magnifier(); sys.exit(app.exec())
    except Exception as e: log_msg(f"FATAL ERROR: {e}"); restore_cursors()
