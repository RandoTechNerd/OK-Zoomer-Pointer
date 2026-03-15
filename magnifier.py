import sys
import ctypes
import traceback
import os
import time
import winreg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QSlider, QPushButton, QColorDialog, 
                             QSystemTrayIcon, QMenu, QFrame, QCheckBox, QRadioButton, QButtonGroup)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QPointF, QRect, QRectF, QSettings, QSharedMemory, QUrl)
from PyQt6.QtGui import (QPainter, QBrush, QPen, QColor, QPixmap, 
                         QPainterPath, QCursor, QAction, QIcon, QGuiApplication, QDesktopServices)

# App Constants
APP_NAME = "OK Zoomer"
APP_ID = "RandoTechNerd.OKZoomer.V2.1"
LOG_FILE = "OK_ZOOMER_LOG.txt"
VERSION = "V2.1 Stable"

# Windows API Constants
SPI_SETCURSORS = 0x0057
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Virtual Keys
VK_ALT, VK_SHIFT, VK_MBUTTON = 0x12, 0x10, 0x04
VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT = 0x26, 0x28, 0x25, 0x27
VK_COMMA, VK_PERIOD, VK_C, VK_SLASH, VK_CONTROL = 0xBC, 0xBE, 0x43, 0xBF, 0x11
VK_0, VK_1, VK_2, VK_3, VK_4, VK_8 = 0x30, 0x31, 0x32, 0x33, 0x34, 0x38
VK_NUM0, VK_NUM1, VK_NUM2, VK_NUM3, VK_NUM4, VK_NUM8 = 0x60, 0x61, 0x62, 0x63, 0x64, 0x68

# Modes
STYLE_NORMAL, STYLE_HIDDEN, STYLE_LASER, STYLE_CROSSHAIR = 0, 1, 2, 3
CAP_STEALTH, CAP_RECORD, CAP_TRIP = 0, 1, 2
SHAPE_CIRCLE, SHAPE_SQUARE, SHAPE_RECTANGLE = 0, 1, 2

RAINBOW_COLORS = [
    "#FF0000", "#FF7F00", "#FFFF00", "#00FF00", "#0000FF", 
    "#4B0082", "#9400D3", "#FFC0CB", "#39FF14"
]

GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

def log_msg(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except: pass

def is_key_pressed(vk):
    try: return bool(GetAsyncKeyState(int(vk)) & 0x8000)
    except: return False

def set_dpi_aware():
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        log_msg("DPI Awareness: Per-Monitor V2")
    except:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            log_msg("DPI Awareness: Per-Monitor")
        except:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                log_msg("DPI Awareness: System")
            except:
                log_msg("DPI Awareness: Failed")

def restore_cursors():
    ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)

def create_blank_cursor():
    and_mask = (ctypes.c_ubyte * 128)(*(0xFF for _ in range(128)))
    xor_mask = (ctypes.c_ubyte * 128)(*(0x00 for _ in range(128)))
    return ctypes.windll.user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)

def get_magnifier_icon():
    pix = QPixmap(128, 128); pix.fill(Qt.GlobalColor.transparent); p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(QPen(QColor("#3498db"), 8))
    p.setBrush(QBrush(QColor(255, 255, 255, 50))); p.drawEllipse(15, 15, 80, 80); p.drawLine(85, 85, 115, 115)
    p.setPen(QPen(Qt.GlobalColor.black, 4)); p.setBrush(QBrush(Qt.GlobalColor.white))
    path = QPainterPath(); path.moveTo(40, 40); path.lineTo(65, 55); path.lineTo(55, 55)
    path.lineTo(65, 75); path.lineTo(58, 78); path.lineTo(48, 58); path.lineTo(40, 70); path.closeSubpath()
    p.drawPath(path); p.end(); return QIcon(pix)

class SettingsWindow(QWidget):
    def __init__(self, magnifier):
        super().__init__()
        self.magnifier = magnifier
        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setWindowIcon(get_magnifier_icon())
        self.setFixedSize(450, 900); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(); header = QHBoxLayout(); logo = QLabel()
        icon = get_magnifier_icon(); logo.setPixmap(icon.pixmap(80, 80)); header.addWidget(logo)
        vbox = QVBoxLayout(); vbox.addWidget(QLabel(f"<h1 style='margin:0;'>{APP_NAME}</h1>"))
        link = QLabel("<a href='https://github.com/RandoTechNerd' style='color:#3498db; text-decoration:none;'>by RandoTechNerd</a>")
        link.setOpenExternalLinks(True); vbox.addWidget(link); header.addLayout(vbox); header.addStretch(); layout.addLayout(header)
        info = QLabel(f"<b>{VERSION}</b><br>• Hold Alt to Zoom<br>• Arrows: Up/Down=Zoom, L/R=Size<br>• 0: Pointer | 4: Shape | 8: Spotlight<br>• 1: White (Double-Tap: Clear) | 2: Rainbow | 3: Black"); info.setWordWrap(True); layout.addWidget(info)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); layout.addWidget(line)
        
        layout.addWidget(QLabel("<b>Activation Keys:</b>")); kl = QHBoxLayout()
        self.alt_cb = QPushButton("Alt"); self.shift_cb = QPushButton("Shift"); self.mid_cb = QPushButton("Mid-Mouse")
        for cb in [self.alt_cb, self.shift_cb, self.mid_cb]: cb.setCheckable(True); cb.clicked.connect(self.update_keys); kl.addWidget(cb)
        layout.addLayout(kl)
        
        layout.addWidget(QLabel("<b>Magnifier Shape:</b>")); hl = QHBoxLayout(); self.shape_group = QButtonGroup(self)
        shapes = [("Circle", SHAPE_CIRCLE), ("Square", SHAPE_SQUARE), ("Rectangle", SHAPE_RECTANGLE)]
        for label, sid in shapes:
            rb = QRadioButton(label); self.shape_group.addButton(rb, sid); rb.setChecked(self.magnifier.shape == sid)
            rb.clicked.connect(self.update_shape); hl.addWidget(rb)
        layout.addLayout(hl)

        layout.addWidget(QLabel("<b>Pointer Style:</b>")); sl = QHBoxLayout(); self.style_group = QButtonGroup(self)
        styles = [("Normal", STYLE_NORMAL), ("Hidden", STYLE_HIDDEN), ("Laser", STYLE_LASER), ("Crosshair", STYLE_CROSSHAIR)]
        for label, sid in styles:
            rb = QRadioButton(label); self.style_group.addButton(rb, sid); rb.setChecked(self.magnifier.pointer_style == sid)
            rb.clicked.connect(self.update_style); sl.addWidget(rb)
        layout.addLayout(sl); self.spotlight_cb = QCheckBox("Spotlight Mode (Dim screen)"); self.spotlight_cb.setChecked(self.magnifier.spotlight_enabled); self.spotlight_cb.toggled.connect(self.update_spotlight); layout.addWidget(self.spotlight_cb)
        
        layout.addWidget(QLabel("Default Zoom:")); self.zoom_s = QSlider(Qt.Orientation.Horizontal); self.zoom_s.setRange(11, 150); self.zoom_s.setValue(int(self.magnifier.zoom*10)); self.zoom_s.valueChanged.connect(self.update_zoom); layout.addWidget(self.zoom_s)
        layout.addWidget(QLabel("Magnifier Width:")); self.radius_s = QSlider(Qt.Orientation.Horizontal); self.radius_s.setRange(50, 600); self.radius_s.setValue(self.magnifier.radius); self.radius_s.valueChanged.connect(self.update_radius); layout.addWidget(self.radius_s)
        
        cl = QHBoxLayout(); self.color_btn = QPushButton("Change Color"); self.color_btn.clicked.connect(self.pick_color)
        self.clear_btn = QPushButton("Set CLEAR"); self.clear_btn.setCheckable(True); self.clear_btn.clicked.connect(self.set_clear_color)
        cl.addWidget(self.color_btn); cl.addWidget(self.clear_btn); layout.addLayout(cl)
        
        # ADVANCED OPTIONS (Collapsible)
        self.adv_btn = QPushButton("Advanced Options ▼"); self.adv_btn.setFlat(True); self.adv_btn.setStyleSheet("text-align:left; font-weight:bold; color:#7f8c8d;"); self.adv_btn.clicked.connect(self.toggle_advanced); layout.addWidget(self.adv_btn)
        self.adv_frame = QFrame(); self.adv_layout = QVBoxLayout(self.adv_frame); self.adv_frame.setVisible(False)
        
        self.adv_layout.addWidget(QLabel("<b>Performance (Refresh FPS):</b>"))
        self.rate_s = QSlider(Qt.Orientation.Horizontal); self.rate_s.setRange(10, 100); 
        self.rate_s.setValue(int(1000/self.magnifier.tick_rate)); self.rate_s.valueChanged.connect(self.update_rate); self.adv_layout.addWidget(self.rate_s)
        self.rate_l = QLabel(f"Smoothness: {int(1000/self.magnifier.tick_rate)} FPS"); self.adv_layout.addWidget(self.rate_l)
        
        self.adv_layout.addWidget(QLabel("<b>Capture Mode:</b>"))
        self.cap_group = QButtonGroup(self); caps = [("Stealth (Hidden from recording)", CAP_STEALTH), ("Standard Record (Visible)", CAP_RECORD), ("Trip Mode (Recursive)", CAP_TRIP)]
        for label, cid in caps:
            rb = QRadioButton(label); self.cap_group.addButton(rb, cid); rb.setChecked(self.magnifier.capture_mode == cid)
            rb.clicked.connect(self.update_capture); self.adv_layout.addWidget(rb)
        layout.addWidget(self.adv_frame)
        
        layout.addStretch()
        fl = QHBoxLayout(); yt = QPushButton("YouTube"); yt.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://youtube.com/@RandoTechNerd")))
        coffee = QPushButton("☕ Buy Coffee"); coffee.setStyleSheet("background-color:#f1c40f;font-weight:bold;"); coffee.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/randotechnerd")))
        fl.addWidget(yt); fl.addWidget(coffee); layout.addLayout(fl)
        self.apply_btn = QPushButton("Apply & Save"); self.apply_btn.clicked.connect(self.hide); self.apply_btn.setStyleSheet("background-color:#3498db;color:white;font-weight:bold;padding:10px;"); layout.addWidget(self.apply_btn)
        self.setLayout(layout); self.refresh_ui()

    def toggle_advanced(self):
        visible = not self.adv_frame.isVisible()
        self.adv_frame.setVisible(visible)
        self.adv_btn.setText("Advanced Options ▲" if visible else "Advanced Options ▼")

    def update_rate(self, v):
        ms = int(1000/max(1, v))
        self.magnifier.tick_rate = ms; self.rate_l.setText(f"Smoothness: {v} FPS"); self.magnifier.timer.setInterval(ms); self.magnifier.save_settings()
    
    def refresh_ui(self):
        self.alt_cb.setChecked(VK_ALT in self.magnifier.activation_keys); self.shift_cb.setChecked(VK_SHIFT in self.magnifier.activation_keys); self.mid_cb.setChecked(VK_MBUTTON in self.magnifier.activation_keys)
        is_clear = self.magnifier.border_color.alpha() == 0
        self.clear_btn.setChecked(is_clear)
        self.clear_btn.setText("CLEAR ✓" if is_clear else "Set CLEAR")
        
    def update_keys(self):
        keys = []
        if self.alt_cb.isChecked(): keys.append(VK_ALT)
        if self.shift_cb.isChecked(): keys.append(VK_SHIFT)
        if self.mid_cb.isChecked(): keys.append(VK_MBUTTON)
        if not keys: self.alt_cb.setChecked(True); keys = [VK_ALT]
        self.magnifier.activation_keys = keys; self.magnifier.save_settings(); self.refresh_ui()
    def update_capture(self): self.magnifier.capture_mode = self.cap_group.checkedId(); self.magnifier.save_settings(); self.magnifier.apply_capture_flags()
    def update_shape(self): self.magnifier.shape = self.shape_group.checkedId(); self.magnifier.save_settings(); self.magnifier.update_window_size()
    def update_style(self): self.magnifier.pointer_style = self.style_group.checkedId(); self.magnifier.save_settings(); self.magnifier.force_cursor_update()
    def update_spotlight(self, v): self.magnifier.spotlight_enabled = v; self.magnifier.save_settings(); self.magnifier.update_window_size()
    def update_zoom(self, v): self.magnifier.zoom = v / 10.0; self.magnifier.save_settings()
    def update_radius(self, v): self.magnifier.radius = v; self.magnifier.update_window_size(); self.magnifier.save_settings()
    def pick_color(self):
        c = QColorDialog.getColor(self.magnifier.border_color, self, "Pick Color")
        if c.isValid(): self.magnifier.border_color = c; self.magnifier.save_settings(); self.refresh_ui()
    def set_clear_color(self):
        if self.clear_btn.isChecked(): self.magnifier.border_color = QColor(0, 0, 0, 0)
        else: self.magnifier.border_color = QColor("#00FF00")
        self.magnifier.save_settings(); self.refresh_ui()

class Magnifier(QWidget):
    def __init__(self):
        super().__init__()
        try:
            self.settings_manager = QSettings("RTN", "OK_Zoomer_V2.1")
            self.tick_rate = int(self.settings_manager.value("tick_rate", 16))
            self.load_settings(); self.pix = None; self._is_active = False
            self._last_c, self._last_slash = False, False; self._cursor_hidden = False; self._cache = None
            self._last_0, self._last_1, self._last_2, self._last_3, self._last_4, self._last_8 = False, False, False, False, False, False
            self._last_1_time = 0; self._grab_pos = QPoint(0, 0); self._locked_geom = QRect()
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            self.update_window_size(); self.apply_capture_flags()
            self.tray_dummy = QWidget(); self.tray = QSystemTrayIcon(self.tray_dummy); self.update_tray(False)
            self.menu = QMenu(self.tray_dummy); self.menu.addAction("Settings", self.show_settings)
            self.menu.addSeparator(); self.menu.addAction(f"Exit", self.emergency_exit)
            self.tray.setContextMenu(self.menu); self.tray.show()
            self.timer = QTimer(); self.timer.timeout.connect(self.tick); self.timer.start(self.tick_rate)
            self.settings_window = SettingsWindow(self); self.hide(); log_msg(f"{VERSION} Started.")
        except Exception as e: log_msg(f"INIT ERROR: {e}\n{traceback.format_exc()}")

    def load_settings(self):
        self.zoom = float(self.settings_manager.value("zoom", 2.0))
        self.radius = int(self.settings_manager.value("radius", 150))
        self.opacity = float(self.settings_manager.value("opacity", 1.0))
        self.border_color = QColor(self.settings_manager.value("color", "#00FF00"))
        self.pointer_style = int(self.settings_manager.value("pointer_style", STYLE_NORMAL))
        self.shape = int(self.settings_manager.value("shape", SHAPE_CIRCLE))
        self.spotlight_enabled = str(self.settings_manager.value("spotlight", "false")).lower() == "true"
        self.capture_mode = int(self.settings_manager.value("capture_mode", CAP_RECORD))
        self.color_cycle_idx = int(self.settings_manager.value("color_cycle_idx", 0))
        keys = self.settings_manager.value("activation_keys", [VK_ALT, VK_MBUTTON])
        if isinstance(keys, str): keys = [int(keys)]
        try: self.activation_keys = [int(k) for k in keys if int(k) != VK_CONTROL]
        except: self.activation_keys = [VK_ALT, VK_MBUTTON]
        if not self.activation_keys: self.activation_keys = [VK_ALT]

    def save_settings(self):
        self.settings_manager.setValue("zoom", self.zoom); self.settings_manager.setValue("radius", self.radius); self.settings_manager.setValue("opacity", self.opacity); self.settings_manager.setValue("color", self.border_color.name(QColor.NameFormat.HexArgb)); self.settings_manager.setValue("pointer_style", self.pointer_style); self.settings_manager.setValue("shape", self.shape); self.settings_manager.setValue("spotlight", self.spotlight_enabled); self.settings_manager.setValue("capture_mode", self.capture_mode); self.settings_manager.setValue("activation_keys", self.activation_keys); self.settings_manager.setValue("color_cycle_idx", self.color_cycle_idx); self.settings_manager.setValue("tick_rate", self.tick_rate)

    def update_window_size(self):
        self.setMinimumSize(0, 0); self.setMaximumSize(16777215, 16777215)
        if self.spotlight_enabled:
            user32 = ctypes.windll.user32
            vx = user32.GetSystemMetrics(76)
            vy = user32.GetSystemMetrics(77)
            vw = user32.GetSystemMetrics(78)
            vh = user32.GetSystemMetrics(79)
            if vw == 0 or vh == 0:
                v_geom = QRect()
                for s in QGuiApplication.screens(): v_geom = v_geom.united(s.geometry())
                vx, vy, vw, vh = v_geom.x(), v_geom.y(), v_geom.width(), v_geom.height()
            self._locked_geom = QRect(vx, vy, vw, vh)
            hwnd = int(self.winId())
            user32.SetWindowPos(hwnd, -1, vx, vy, vw, vh, 0x0040)
            self.setGeometry(self._locked_geom)
        else:
            w, h = int(self.radius * 2 + 100), int(self.radius * 2 + 100)
            if self.shape == SHAPE_RECTANGLE: w = int(w * 1.5)
            self.setFixedSize(w, h)
        self.setWindowOpacity(self.opacity)

    def apply_capture_flags(self):
        try:
            hwnd = self.winId().__int__()
            flag = 0x00000011 if self.capture_mode == CAP_STEALTH else 0x00000000
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, flag)
        except: pass

    def update_tray(self, active):
        pix = QPixmap(32, 32); pix.fill(Qt.GlobalColor.transparent); p = QPainter(pix)
        p.setBrush(QBrush(QColor("#2ecc71") if active else QColor("#e74c3c"))); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(4, 4, 24, 24); p.end(); self.tray.setIcon(QIcon(pix))

    def show_settings(self):
        self.settings_window.refresh_ui()
        self.settings_window.show()
        # Force to front
        self.settings_window.setWindowState(self.settings_window.windowState() & ~Qt.WindowState.WindowMinimized | Qt.WindowState.WindowActive)
        self.settings_window.raise_()
        self.settings_window.activateWindow()
        ctypes.windll.user32.SetForegroundWindow(int(self.settings_window.winId()))

    def force_cursor_update(self):
        if self._is_active: self.toggle_global_cursor(self.pointer_style != STYLE_NORMAL)
    def toggle_global_cursor(self, hide):
        if hide and not self._cursor_hidden:
            blank = create_blank_cursor()
            for cid in [32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644, 32645, 32646, 32648, 32649, 32511]:
                ctypes.windll.user32.SetSystemCursor(ctypes.windll.user32.CopyImage(blank, 2, 0, 0, 0), cid)
            self._cursor_hidden = True
        elif not hide and self._cursor_hidden: restore_cursors(); self._cursor_hidden = False

    def set_active(self, state):
        if self._is_active != state:
            self._is_active = state; self.update_tray(state)
            if state:
                if self.capture_mode == CAP_RECORD:
                    self.hide(); QApplication.processEvents(); time.sleep(0.02)
                    pos = QCursor.pos(); screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
                    self._cache = screen.grabWindow(0); self._cache_rect = screen.geometry()
                self.update_window_size(); self.show(); self.raise_()
            if self.pointer_style != STYLE_NORMAL: self.toggle_global_cursor(state)
            if not state: self.hide(); self._cache = None

    def emergency_exit(self): restore_cursors(); QApplication.instance().quit()

    def tick(self):
        try:
            is_down = any(is_key_pressed(int(key)) for key in self.activation_keys)
            self.set_active(is_down)
            if is_down:
                k0 = is_key_pressed(VK_0) or is_key_pressed(VK_NUM0)
                if k0 and not self._last_0:
                    self.pointer_style = (self.pointer_style + 1) % 4; self.save_settings(); self.force_cursor_update()
                    for i in range(4):
                        b = self.settings_window.style_group.button(i)
                        if b: b.setChecked(i == self.pointer_style)
                self._last_0 = k0
                k4 = is_key_pressed(VK_4) or is_key_pressed(VK_NUM4)
                if k4 and not self._last_4:
                    self.shape = (self.shape + 1) % 3; self.save_settings(); self.update_window_size()
                    for i in range(3):
                        b = self.settings_window.shape_group.button(i)
                        if b: b.setChecked(i == self.shape)
                self._last_4 = k4
                k8 = is_key_pressed(VK_8) or is_key_pressed(VK_NUM8)
                if k8 and not self._last_8:
                    self.spotlight_enabled = not self.spotlight_enabled; self.save_settings(); self.update_window_size()
                    self.settings_window.spotlight_cb.setChecked(self.spotlight_enabled)
                self._last_8 = k8
                k1 = is_key_pressed(VK_1) or is_key_pressed(VK_NUM1)
                if k1 and not self._last_1:
                    now = time.time()
                    if now - self._last_1_time < 0.3: self.border_color = QColor(0, 0, 0, 0)
                    else: self.border_color = QColor("#FFFFFF")
                    self._last_1_time = now; self.save_settings(); self.settings_window.refresh_ui()
                self._last_1 = k1
                k2 = is_key_pressed(VK_2) or is_key_pressed(VK_NUM2)
                if k2 and not self._last_2:
                    self.border_color = QColor(RAINBOW_COLORS[self.color_cycle_idx])
                    self.color_cycle_idx = (self.color_cycle_idx + 1) % len(RAINBOW_COLORS); self.save_settings(); self.settings_window.refresh_ui()
                self._last_2 = k2
                k3 = is_key_pressed(VK_3) or is_key_pressed(VK_NUM3)
                if k3 and not self._last_3: self.border_color = QColor("#000000"); self.save_settings(); self.settings_window.refresh_ui()
                self._last_3 = k3
                if is_key_pressed(VK_UP): self.zoom = min(15.0, self.zoom + 0.05)
                if is_key_pressed(VK_DOWN): self.zoom = max(1.1, self.zoom - 0.05)
                if is_key_pressed(VK_RIGHT): self.radius = min(600, self.radius + 3); self.update_window_size()
                if is_key_pressed(VK_LEFT): self.radius = max(50, self.radius - 3); self.update_window_size()
                sl_p = is_key_pressed(VK_SLASH)
                if sl_p and not self._last_slash:
                    self.spotlight_enabled = not self.spotlight_enabled; self.save_settings(); self.update_window_size(); self.settings_window.spotlight_cb.setChecked(self.spotlight_enabled)
                self._last_slash = sl_p
            if not self._is_active: return
            if is_key_pressed(VK_COMMA): self.opacity = max(0.1, self.opacity - 0.02); self.setWindowOpacity(self.opacity)
            if is_key_pressed(VK_PERIOD): self.opacity = min(1.0, self.opacity + 0.02); self.setWindowOpacity(self.opacity)
            pos = QCursor.pos(); self._grab_pos = pos
            screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
            if self.spotlight_enabled and self.geometry() != self._locked_geom: self.setGeometry(self._locked_geom)
            elif not self.spotlight_enabled: self.move(int(pos.x() - self.width() / 2.0), int(pos.y() - self.height() / 2.0))
            if screen:
                rw, rh = self.radius, self.radius
                if self.shape == SHAPE_RECTANGLE: rw = int(rw * 1.5)
                cw, ch = int((rw * 2) / self.zoom), int((rh * 2) / self.zoom)
                gx, gy = pos.x() - cw // 2, pos.y() - ch // 2
                if self.capture_mode == CAP_RECORD and self._cache:
                    s_rect = self._cache_rect; raw_grab = self._cache.copy(gx - s_rect.x(), gy - s_rect.y(), cw, ch)
                else: raw_grab = screen.grabWindow(0, gx, gy, cw, ch)
                if raw_grab.width() != cw or raw_grab.height() != ch:
                    padded = QPixmap(cw, ch); padded.fill(Qt.GlobalColor.black); p_pad = QPainter(padded)
                    s_geom = screen.geometry(); dx = max(0, s_geom.x() - gx); dy = max(0, s_geom.y() - gy)
                    p_pad.drawPixmap(dx, dy, raw_grab); p_pad.end(); self.pix = padded
                else: self.pix = raw_grab
                self.update()
        except Exception as e: log_msg(f"TICK ERROR: {e}\n{traceback.format_exc()}")

    def paintEvent(self, event):
        if not self._is_active or self.pix is None: return
        try:
            p = QPainter(self); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
            local_pos = self.mapFromGlobal(self._grab_pos); center = QPointF(local_pos)
            rw, rh = float(self.radius), float(self.radius)
            if self.shape == SHAPE_RECTANGLE: rw *= 1.5
            path = QPainterPath()
            if self.shape == SHAPE_CIRCLE: path.addEllipse(center, rw, rh)
            else: path.addRect(center.x() - rw, center.y() - rh, rw * 2, rh * 2)
            if self.spotlight_enabled:
                p.fillRect(self.rect(), QColor(0, 0, 0, 180)); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                p.drawPath(path); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setClipPath(path)
            if not self.spotlight_enabled: p.fillRect(self.rect(), QColor(0, 0, 0, int(self.opacity * 255)))
            p.drawPixmap(QRectF(center.x() - rw, center.y() - rh, rw * 2, rh * 2).toRect(), self.pix)
            p.setClipping(False); p.setPen(QPen(self.border_color, 5)); p.drawPath(path)
            if self.pointer_style == STYLE_LASER:
                p.setBrush(QBrush(QColor(255, 0, 0, 200))); p.setPen(QPen(QColor(255, 255, 255, 150), 2))
                p.drawEllipse(center, 5, 5); p.setPen(QPen(QColor(255, 0, 0, 100), 10)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(center, 8, 8)
            elif self.pointer_style == STYLE_CROSSHAIR:
                p.setPen(QPen(self.border_color, 2)); l = 20; p.drawLine(QPointF(center.x() - l, center.y()), QPointF(center.x() + l, center.y())); p.drawLine(QPointF(center.x(), center.y() - l), QPointF(center.x(), center.y() + l)); p.drawEllipse(center, 10, 10)
        except Exception as e: log_msg(f"PAINT ERROR: {e}")

if __name__ == "__main__":
    # Fix for taskbar icon (Set AppUserModelID)
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except: pass
    
    set_dpi_aware(); restore_cursors(); app = QApplication(sys.argv)
    
    # Force procedural icon globally
    app.setWindowIcon(get_magnifier_icon())
    
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"): app.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    shared_mem = QSharedMemory(APP_ID); 
    if not shared_mem.create(1): sys.exit(0)
    app.setQuitOnLastWindowClosed(False); app.aboutToQuit.connect(restore_cursors)
    try: m = Magnifier(); sys.exit(app.exec())
    except Exception as e: log_msg(f"FATAL ERROR: {e}"); restore_cursors()
