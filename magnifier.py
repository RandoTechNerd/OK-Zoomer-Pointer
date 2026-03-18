import sys
import ctypes
import traceback
import os
import time
import winreg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QSlider, QPushButton, QColorDialog, 
                             QSystemTrayIcon, QMenu, QFrame, QCheckBox, QRadioButton, 
                             QButtonGroup, QScrollArea)
from PyQt6.QtCore import (Qt, QTimer, QPoint, QPointF, QRect, QRectF, QSettings, QSharedMemory, QUrl, QProcess)
from PyQt6.QtGui import (QPainter, QBrush, QPen, QColor, QPixmap, QImage,
                         QPainterPath, QCursor, QAction, QIcon, QGuiApplication, QDesktopServices)

# ==========================================
# 1. CONSTANTS
# ==========================================
APP_NAME = "OK Zoomer Boom Supreme"
APP_ID = "RandoTechNerd.OKZoomer.Boom.Supreme.V3.1"
LOG_FILE = "OK_ZOOMER_LOG.txt"
VERSION = "V3.1 Boom Supreme"

VK_ALT, VK_SHIFT, VK_MBUTTON = 0x12, 0x10, 0x04
VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT = 0x26, 0x28, 0x25, 0x27
VK_COMMA, VK_PERIOD, VK_C, VK_SLASH, VK_CONTROL = 0xBC, 0xBE, 0x43, 0xBF, 0x11
VK_0, VK_1, VK_2, VK_3, VK_4, VK_8 = 0x30, 0x31, 0x32, 0x33, 0x34, 0x38
VK_NUM0, VK_NUM1, VK_NUM2, VK_NUM3, VK_NUM4, VK_NUM8 = 0x60, 0x61, 0x62, 0x63, 0x64, 0x68

STYLE_NORMAL, STYLE_HIDDEN, STYLE_LASER, STYLE_CROSSHAIR = 0, 1, 2, 3
CAP_STEALTH, CAP_PRESENTATION = 0, 1
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

class SettingsWindow(QWidget):
    def __init__(self, magnifier):
        super().__init__()
        self.magnifier = magnifier; self.setWindowTitle(f"{APP_NAME} Settings"); self.setWindowIcon(get_magnifier_icon())
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint); self.base_w, self.base_h = 550, 700
        
        main_layout = QVBoxLayout(self)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget(); layout = QVBoxLayout(self.container)
        
        header = QHBoxLayout(); logo = QLabel(); logo.setPixmap(get_magnifier_icon().pixmap(80, 80)); header.addWidget(logo)
        vbox = QVBoxLayout(); vbox.addWidget(QLabel(f"<h1 style='margin:0;'>{APP_NAME}</h1>"))
        vbox.addWidget(QLabel(f"<b>{VERSION}</b>"))
        header.addLayout(vbox); header.addStretch(); layout.addLayout(header)
        
        info = QLabel(f"• Hold Alt to Zoom.<br>• Use <b>Presentation Mode</b> for Zoom/OBS screen sharing.<br>• Adjust DPI Factor if zoom is misaligned.")
        info.setWordWrap(True); layout.addWidget(info)
        
        layout.addWidget(QLabel("<b>Capture Mode:</b>")); self.cap_group = QButtonGroup(self)
        r1 = QRadioButton("STEALTH (Invisible)"); self.cap_group.addButton(r1, CAP_STEALTH); layout.addWidget(r1)
        r2 = QRadioButton("PRESENTATION (Visible to OBS)"); r2.setStyleSheet("font-weight: bold; color: #27ae60;"); self.cap_group.addButton(r2, CAP_PRESENTATION); layout.addWidget(r2)
        r1.clicked.connect(self.update_capture); r2.clicked.connect(self.update_capture)
        
        layout.addSpacing(10); self.adv_btn = QPushButton("Calibration Tools ▼"); self.adv_btn.setFlat(True); self.adv_btn.setStyleSheet("text-align:left; font-weight:bold; color:#3498db;"); self.adv_btn.clicked.connect(self.toggle_advanced); layout.addWidget(self.adv_btn)
        self.adv_frame = QFrame(); self.adv_layout = QVBoxLayout(self.adv_frame); self.adv_frame.setVisible(False)
        self.adv_layout.addWidget(QLabel("<b>DPI Override (1.5 = 150% scaling):</b>"))
        self.dpi_s = QSlider(Qt.Orientation.Horizontal); self.dpi_s.setRange(10, 30); self.dpi_s.valueChanged.connect(self.update_dpi); self.adv_layout.addWidget(self.dpi_s)
        self.dpi_l = QLabel(""); self.adv_layout.addWidget(self.dpi_l)
        self.offx_s = QSlider(Qt.Orientation.Horizontal); self.offx_s.setRange(-200, 200); self.offx_s.valueChanged.connect(self.update_offset_x); self.adv_layout.addWidget(QLabel("Horizontal Fine-Tune:")); self.adv_layout.addWidget(self.offx_s)
        self.offy_s = QSlider(Qt.Orientation.Horizontal); self.offy_s.setRange(-200, 200); self.offy_s.valueChanged.connect(self.update_offset_y); self.adv_layout.addWidget(QLabel("Vertical Fine-Tune:")); self.adv_layout.addWidget(self.offy_s)
        layout.addWidget(self.adv_frame)

        layout.addWidget(QLabel("<br><b>Activation Keys:</b>")); kl = QHBoxLayout()
        self.alt_cb = QPushButton("Alt"); self.shift_cb = QPushButton("Shift"); self.mid_cb = QPushButton("Mid-Mouse")
        for cb in [self.alt_cb, self.shift_cb, self.mid_cb]: cb.setCheckable(True); cb.clicked.connect(self.update_keys); kl.addWidget(cb)
        layout.addLayout(kl); layout.addWidget(QLabel("<b>Magnifier Shape:</b>")); hl = QHBoxLayout(); self.shape_group = QButtonGroup(self)
        for label, sid in [("Circle", SHAPE_CIRCLE), ("Square", SHAPE_SQUARE), ("Rectangle", SHAPE_RECTANGLE)]:
            rb = QRadioButton(label); self.shape_group.addButton(rb, sid); rb.clicked.connect(self.update_shape); hl.addWidget(rb)
        layout.addLayout(hl); layout.addWidget(QLabel("<b>Pointer Style:</b>")); sl = QHBoxLayout(); self.style_group = QButtonGroup(self)
        for label, sid in [("Normal", STYLE_NORMAL), ("Hidden", STYLE_HIDDEN), ("Laser", STYLE_LASER), ("Crosshair", STYLE_CROSSHAIR)]:
            rb = QRadioButton(label); self.style_group.addButton(rb, sid); rb.clicked.connect(self.update_style); sl.addWidget(rb)
        layout.addLayout(sl)
        
        layout.addWidget(QLabel("Default Zoom:")); self.zoom_s = QSlider(Qt.Orientation.Horizontal); self.zoom_s.setRange(11, 150); self.zoom_s.valueChanged.connect(self.update_zoom); layout.addWidget(self.zoom_s)
        layout.addWidget(QLabel("Magnifier Size:")); self.radius_s = QSlider(Qt.Orientation.Horizontal); self.radius_s.setRange(50, 600); self.radius_s.setValue(self.magnifier.radius); self.radius_s.valueChanged.connect(self.update_radius); layout.addWidget(self.radius_s)
        
        layout.addSpacing(10); self.apply_btn = QPushButton("Save & Close"); self.apply_btn.clicked.connect(self.hide); self.apply_btn.setStyleSheet("background-color:#2c3e50;color:white;font-weight:bold;padding:10px;"); layout.addWidget(self.apply_btn)
        self.restart_btn = QPushButton("♻ RESTART APP"); self.restart_btn.setStyleSheet("background-color:#e67e22; color:white; font-weight:bold;"); self.restart_btn.clicked.connect(self.magnifier.restart_app); layout.addWidget(self.restart_btn)
        
        layout.addStretch()
        self.scroll.setWidget(self.container); main_layout.addWidget(self.scroll); self.setLayout(main_layout); self.apply_scaling(); self.refresh_ui()

    def apply_scaling(self):
        screen = QGuiApplication.primaryScreen(); ratio = screen.devicePixelRatio()
        self.setFixedSize(int(self.base_w * ratio), min(int(self.base_h * ratio), int(screen.availableGeometry().height() * 0.9)))
    def toggle_advanced(self): self.adv_frame.setVisible(not self.adv_frame.isVisible())
    def refresh_ui(self):
        self.alt_cb.setChecked(VK_ALT in self.magnifier.activation_keys); self.shift_cb.setChecked(VK_SHIFT in self.magnifier.activation_keys); self.mid_cb.setChecked(VK_MBUTTON in self.magnifier.activation_keys)
        if self.shape_group.button(self.magnifier.shape): self.shape_group.button(self.magnifier.shape).setChecked(True)
        if self.style_group.button(self.magnifier.pointer_style): self.style_group.button(self.magnifier.pointer_style).setChecked(True)
        if self.cap_group.button(self.magnifier.capture_mode): self.cap_group.button(self.magnifier.capture_mode).setChecked(True)
        self.zoom_s.setValue(int(self.magnifier.zoom * 10)); self.radius_s.setValue(self.magnifier.radius)
        self.offx_s.setValue(self.magnifier.pull_x); self.offy_s.setValue(self.magnifier.pull_y)
        self.dpi_s.setValue(int(self.magnifier.dpi_override * 10)); self.dpi_l.setText(f"Factor: {self.magnifier.dpi_override}x")
    def update_dpi(self, v): self.magnifier.dpi_override = v / 10.0; self.dpi_l.setText(f"Factor: {self.magnifier.dpi_override}x"); self.magnifier.save_settings()
    def update_keys(self):
        keys = []; [keys.append(k) for k, b in [(VK_ALT, self.alt_cb.isChecked()), (VK_SHIFT, self.shift_cb.isChecked()), (VK_MBUTTON, self.mid_cb.isChecked())] if b]
        if not keys: self.alt_cb.setChecked(True); keys = [VK_ALT]
        self.magnifier.activation_keys = keys; self.magnifier.save_settings(); self.refresh_ui()
    def update_capture(self, v): self.magnifier.capture_mode = self.cap_group.checkedId(); self.magnifier.save_settings(); self.magnifier.apply_capture_flags()
    def update_offset_x(self, v): self.magnifier.pull_x = v; self.magnifier.save_settings()
    def update_offset_y(self, v): self.magnifier.pull_y = v; self.magnifier.save_settings()
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
            self._last_0, self._last_1, self._last_2, self._last_3, self._last_4, self._last_8 = False, False, False, False, False, False
            self.load_settings(); self._cache = None
            
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            
            self.update_window_size(); self.apply_capture_flags()
            self.tray_dummy = QWidget(); self.tray = QSystemTrayIcon(self.tray_dummy); self.update_tray(False)
            self.menu = QMenu(self.tray_dummy); self.menu.addAction("Settings", self.show_settings); self.menu.addAction("Exit", self.emergency_exit); self.tray.setContextMenu(self.menu); self.tray.show()
            self.timer = QTimer(); self.timer.timeout.connect(self.tick); self.timer.start(self.tick_rate)
            self.settings_window = SettingsWindow(self); self.hide(); QTimer.singleShot(1000, self.show_settings)
            log_msg(f"{VERSION} Started.")
        except Exception as e: log_msg(f"INIT ERROR: {e}\n{traceback.format_exc()}")

    def load_settings(self):
        self.zoom = float(self.settings_manager.value("zoom", 2.0)); self.radius = int(self.settings_manager.value("radius", 150))
        self.border_color = QColor(self.settings_manager.value("color", "#00FF00"))
        self.pointer_style = int(self.settings_manager.value("pointer_style", STYLE_NORMAL)); self.shape = int(self.settings_manager.value("shape", SHAPE_CIRCLE))
        self.capture_mode = int(self.settings_manager.value("capture_mode", CAP_PRESENTATION))
        self.pull_x = int(self.settings_manager.value("pull_x", 0)); self.pull_y = int(self.settings_manager.value("pull_y", 0))
        self.dpi_override = float(self.settings_manager.value("dpi_override", 1.5))
        self.color_cycle_idx = 0; keys = self.settings_manager.value("activation_keys", [VK_ALT, VK_MBUTTON])
        try: self.activation_keys = [int(k) for k in (keys if isinstance(keys, list) else [keys])]
        except: self.activation_keys = [VK_ALT, VK_MBUTTON]

    def save_settings(self):
        self.settings_manager.setValue("zoom", self.zoom); self.settings_manager.setValue("radius", self.radius); self.settings_manager.setValue("color", self.border_color.name(QColor.NameFormat.HexArgb))
        self.settings_manager.setValue("pointer_style", self.pointer_style); self.settings_manager.setValue("shape", self.shape); self.settings_manager.setValue("activation_keys", self.activation_keys)
        self.settings_manager.setValue("capture_mode", self.capture_mode); self.settings_manager.setValue("pull_x", self.pull_x); self.settings_manager.setValue("pull_y", self.pull_y); self.settings_manager.setValue("dpi_override", self.dpi_override)

    def update_window_size(self):
        self.setMinimumSize(0, 0); self.setMaximumSize(16777215, 16777215)
        if self.spotlight_enabled: 
            u32 = ctypes.windll.user32; self.setGeometry(u32.GetSystemMetrics(76), u32.GetSystemMetrics(77), u32.GetSystemMetrics(78), u32.GetSystemMetrics(79))
        else:
            w, h = int(self.radius * 2 + 100), int(self.radius * 2 + 100); w = int(w * 1.5) if self.shape == SHAPE_RECTANGLE else w; self.setFixedSize(w, h)
        self.setWindowOpacity(1.0)

    def apply_capture_flags(self):
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000000 if self.capture_mode == CAP_PRESENTATION else 0x00000011)
        except: pass

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

    def emergency_exit(self): restore_cursors(); QApplication.instance().quit()
    def restart_app(self): restore_cursors(); QProcess.startDetached(sys.executable, [os.path.abspath(__file__)]); QApplication.instance().quit()

    def tick(self):
        try:
            is_down = any(is_key_pressed(int(key)) for key in self.activation_keys)
            
            if is_down and not self._is_active:
                self._is_active = True; self.update_tray(True)
                if self.capture_mode == CAP_PRESENTATION:
                    screen = QGuiApplication.screenAt(QCursor.pos())
                    if not screen: screen = QGuiApplication.primaryScreen()
                    self._cache_rect = screen.geometry(); self._cache = screen.grabWindow(0)
                self.update_window_size(); self.show(); self.raise_()
                if self.pointer_style != STYLE_NORMAL: self.toggle_global_cursor(True)
            elif not is_down and self._is_active:
                self._is_active = False; self.update_tray(False); self.hide(); self._cache = None
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
            pos = QCursor.pos(); self.move(int(pos.x() - self.width() / 2.0), int(pos.y() - self.height() / 2.0))
            sc = self.dpi_override
            rw = int(self.radius * 1.5) if self.shape == SHAPE_RECTANGLE else self.radius
            ocw, och = int((rw * 2) / self.zoom), int((self.radius * 2) / self.zoom)
            gx, gy = pos.x() - (ocw/2.0), pos.y() - (och/2.0)
            
            if self.capture_mode == CAP_PRESENTATION and self._cache:
                px = int((gx - self._cache_rect.x()) * sc) + self.pull_x
                py = int((gy - self._cache_rect.y()) * sc) + self.pull_y
                pw, ph = int(ocw * sc), int(och * sc)
                self.pix = self._cache.copy(int(px), int(py), int(pw), int(ph))
            else:
                screen = QGuiApplication.primaryScreen()
                if screen: self.pix = screen.grabWindow(0, int(gx), int(gy), int(ocw), int(och))
            self.update()
        except Exception as e: log_msg(f"TICK ERROR: {e}")

    def paintEvent(self, event):
        if not self._is_active or self.pix is None: return
        try:
            p = QPainter(self); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
            center = QPointF(self.width()/2.0, self.height()/2.0); rw, rh = float(self.radius), float(self.radius); rw = rw * 1.5 if self.shape == SHAPE_RECTANGLE else rw; path = QPainterPath()
            if self.shape == SHAPE_CIRCLE: path.addEllipse(center, rw, rh)
            else: path.addRect(center.x() - rw, center.y() - rh, rw * 2, rh * 2)
            if self.spotlight_enabled: p.fillRect(self.rect(), QColor(0, 0, 0, 180)); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear); p.drawPath(path); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setClipPath(path); p.fillRect(self.rect(), QColor(0, 0, 0, 255))
            p.drawPixmap(QRectF(center.x() - rw, center.y() - rh, rw * 2, rh * 2), self.pix, QRectF(0, 0, self.pix.width(), self.pix.height()))
            p.setClipping(False); p.setPen(QPen(self.border_color, 5)); p.drawPath(path)
            if self.pointer_style == STYLE_LASER: p.setBrush(QBrush(QColor(255, 0, 0, 200))); p.setPen(QPen(QColor(255, 255, 255, 150), 2)); p.drawEllipse(center, 5, 5); p.setPen(QPen(QColor(255, 0, 0, 100), 10)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(center, 8, 8)
            elif self.pointer_style == STYLE_CROSSHAIR: p.setPen(QPen(self.border_color, 2)); l = 20; p.drawLine(center + QPointF(-l, 0), center + QPointF(l, 0)); p.drawLine(center + QPointF(0, -l), center + QPointF(0, l)); p.drawEllipse(center, 10, 10)
        except Exception as e: log_msg(f"PAINT ERROR: {e}")

if __name__ == "__main__":
    if hasattr(Qt, "HighDpiScaleFactorRoundingPolicy"): QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    set_dpi_aware(); restore_cursors(); app = QApplication(sys.argv); app.setWindowIcon(get_magnifier_icon())
    shared_mem = QSharedMemory(APP_ID); [shared_mem.attach() if not shared_mem.create(1) else None]
    app.setQuitOnLastWindowClosed(False); app.aboutToQuit.connect(restore_cursors)
    try: m = Magnifier(); sys.exit(app.exec())
    except Exception as e: log_msg(f"FATAL ERROR: {e}"); restore_cursors()
