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
APP_ID = "RandoTechNerd.OKZoomer.1.0"
LOG_FILE = "OK_ZOOMER_LOG.txt"

# Windows API Constants
SPI_SETCURSORS = 0x0057
WDA_NONE = 0x00000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Virtual Keys
VK_ALT, VK_SHIFT, VK_MBUTTON = 0x12, 0x10, 0x04
VK_UP, VK_DOWN, VK_LEFT, VK_RIGHT = 0x26, 0x28, 0x25, 0x27
VK_COMMA, VK_PERIOD, VK_C, VK_SLASH, VK_CONTROL = 0xBC, 0xBE, 0x43, 0xBF, 0x11

# Modes
STYLE_NORMAL, STYLE_HIDDEN, STYLE_LASER, STYLE_CROSSHAIR = 0, 1, 2, 3
CAP_STEALTH, CAP_RECORD, CAP_TRIP = 0, 1, 2

GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

def log_msg(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except: pass

def get_windows_sonar():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse")
        val, _ = winreg.QueryValueEx(key, "ClickShowCursorPos")
        winreg.CloseKey(key); return val == "1"
    except: return False

def set_windows_sonar(enabled):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ClickShowCursorPos", 0, winreg.REG_SZ, "1" if enabled else "0")
        winreg.CloseKey(key); ctypes.windll.user32.SystemParametersInfoW(0x101D, 0, enabled, 0)
    except: pass

def restore_cursors():
    ctypes.windll.user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)

def create_blank_cursor():
    and_mask = (ctypes.c_ubyte * 128)(*(0xFF for _ in range(128)))
    xor_mask = (ctypes.c_ubyte * 128)(*(0x00 for _ in range(128)))
    return ctypes.windll.user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)

class SettingsWindow(QWidget):
    def __init__(self, magnifier):
        super().__init__()
        self.magnifier = magnifier
        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setFixedSize(450, 900); self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        layout = QVBoxLayout(); header = QHBoxLayout(); logo = QLabel()
        pix = QPixmap(80, 80); pix.fill(Qt.GlobalColor.transparent); p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(QPen(QColor("#3498db"), 5))
        p.setBrush(QBrush(QColor(255, 255, 255, 50))); p.drawEllipse(10, 10, 50, 50); p.drawLine(52, 52, 70, 70)
        p.setPen(QPen(Qt.GlobalColor.black, 2)); p.setBrush(QBrush(Qt.GlobalColor.white))
        path = QPainterPath(); path.moveTo(25, 25); path.lineTo(40, 35); path.lineTo(33, 35)
        path.lineTo(38, 45); path.lineTo(34, 47); path.lineTo(29, 37); path.lineTo(25, 45); path.closeSubpath()
        p.drawPath(path); p.end(); logo.setPixmap(pix); header.addWidget(logo)
        vbox = QVBoxLayout(); vbox.addWidget(QLabel(f"<h1 style='margin:0;'>{APP_NAME}</h1>"))
        link = QLabel("<a href='https://github.com/RandoTechNerd' style='color:#3498db; text-decoration:none;'>by RandoTechNerd</a>")
        link.setOpenExternalLinks(True); vbox.addWidget(link); header.addLayout(vbox); header.addStretch(); layout.addLayout(header)
        info = QLabel("<b>Controls:</b><br>• Hold Hotkeys to Zoom<br>• Up/Down: Zoom | Left/Right: Size<br>• C: Cycle Style | /: Spotlight"); info.setWordWrap(True); layout.addWidget(info)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); layout.addWidget(line)
        layout.addWidget(QLabel("<b>Activation Keys:</b>")); kl = QHBoxLayout()
        self.alt_cb = QPushButton("Alt"); self.shift_cb = QPushButton("Shift"); self.mid_cb = QPushButton("Mid-Mouse")
        for cb in [self.alt_cb, self.shift_cb, self.mid_cb]: cb.setCheckable(True); cb.clicked.connect(self.update_keys); kl.addWidget(cb)
        layout.addLayout(kl); layout.addWidget(QLabel("<b>Capture Visibility (for Recordings):</b>"))
        self.cap_group = QButtonGroup(self); cl = QVBoxLayout()
        caps = [("Stealth (Hidden from recording)", CAP_STEALTH), ("Standard Record (Visible, no loop)", CAP_RECORD), ("Trip Mode (Visible, recursive loop!)", CAP_TRIP)]
        for label, cid in caps:
            rb = QRadioButton(label); self.cap_group.addButton(rb, cid); rb.setChecked(self.magnifier.capture_mode == cid)
            rb.clicked.connect(self.update_capture); cl.addWidget(rb)
        layout.addLayout(cl); self.sonar_cb = QCheckBox("Enable Windows 'CTRL to Find Mouse' Sonar"); self.sonar_cb.setChecked(get_windows_sonar()); self.sonar_cb.toggled.connect(set_windows_sonar); layout.addWidget(self.sonar_cb)
        layout.addWidget(QLabel("<b>Pointer Style:</b>")); sl = QHBoxLayout(); self.style_group = QButtonGroup(self)
        styles = [("Normal", STYLE_NORMAL), ("Hidden", STYLE_HIDDEN), ("Laser", STYLE_LASER), ("Crosshair", STYLE_CROSSHAIR)]
        for label, sid in styles:
            rb = QRadioButton(label); self.style_group.addButton(rb, sid); rb.setChecked(self.magnifier.pointer_style == sid)
            rb.clicked.connect(self.update_style); sl.addWidget(rb)
        layout.addLayout(sl); self.spotlight_cb = QCheckBox("Spotlight Mode (Dim screen)"); self.spotlight_cb.setChecked(self.magnifier.spotlight_enabled); self.spotlight_cb.toggled.connect(self.update_spotlight); layout.addWidget(self.spotlight_cb)
        layout.addWidget(QLabel("Default Zoom:")); self.zoom_s = QSlider(Qt.Orientation.Horizontal); self.zoom_s.setRange(11, 150); self.zoom_s.setValue(int(self.magnifier.zoom*10)); self.zoom_s.valueChanged.connect(self.update_zoom); layout.addWidget(self.zoom_s)
        layout.addWidget(QLabel("Default Radius:")); self.radius_s = QSlider(Qt.Orientation.Horizontal); self.radius_s.setRange(50, 600); self.radius_s.setValue(self.magnifier.radius); self.radius_s.valueChanged.connect(self.update_radius); layout.addWidget(self.radius_s)
        self.color_btn = QPushButton("Change Color"); self.color_btn.clicked.connect(self.pick_color); layout.addWidget(self.color_btn); layout.addStretch()
        fl = QHBoxLayout(); yt = QPushButton("YouTube"); yt.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://youtube.com/@RandoTechNerd")))
        coffee = QPushButton("☕ Buy Coffee"); coffee.setStyleSheet("background-color:#f1c40f;font-weight:bold;"); coffee.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://buymeacoffee.com/randotechnerd")))
        fl.addWidget(yt); fl.addWidget(coffee); layout.addLayout(fl)
        self.apply_btn = QPushButton("Apply & Save"); self.apply_btn.clicked.connect(self.hide); self.apply_btn.setStyleSheet("background-color:#3498db;color:white;font-weight:bold;padding:10px;"); layout.addWidget(self.apply_btn)
        self.setLayout(layout); self.refresh_key_ui()

    def refresh_key_ui(self):
        self.alt_cb.setChecked(VK_ALT in self.magnifier.activation_keys); self.shift_cb.setChecked(VK_SHIFT in self.magnifier.activation_keys); self.mid_cb.setChecked(VK_MBUTTON in self.magnifier.activation_keys)
    def update_keys(self):
        keys = []
        if self.alt_cb.isChecked(): keys.append(VK_ALT)
        if self.shift_cb.isChecked(): keys.append(VK_SHIFT)
        if self.mid_cb.isChecked(): keys.append(VK_MBUTTON)
        if not keys: self.alt_cb.setChecked(True); keys = [VK_ALT]
        self.magnifier.activation_keys = keys; self.magnifier.save_settings()
    def update_capture(self): self.magnifier.capture_mode = self.cap_group.checkedId(); self.magnifier.save_settings(); self.magnifier.apply_capture_flags()
    def update_style(self): self.magnifier.pointer_style = self.style_group.checkedId(); self.magnifier.save_settings(); self.magnifier.force_cursor_update()
    def update_spotlight(self, v): self.magnifier.spotlight_enabled = v; self.magnifier.save_settings(); self.magnifier.update_window_size()
    def update_zoom(self, v): self.magnifier.zoom = v / 10.0; self.magnifier.save_settings()
    def update_radius(self, v): self.magnifier.radius = v; self.magnifier.update_window_size(); self.magnifier.save_settings()
    def pick_color(self):
        c = QColorDialog.getColor(self.magnifier.border_color, self, "Pick Color")
        if c.isValid(): self.magnifier.border_color = c; self.magnifier.save_settings()

class Magnifier(QWidget):
    def __init__(self):
        super().__init__()
        try:
            self.settings_manager = QSettings("RTN", "OK_Zoomer_Final_V15")
            self.load_settings(); self.pix = None; self._is_active = False
            self._last_c, self._last_slash = False, False; self._cursor_hidden = False; self._cache = None
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.Tool)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
            self.update_window_size(); self.apply_capture_flags()
            self.tray_dummy = QWidget(); self.tray = QSystemTrayIcon(self.tray_dummy); self.update_tray(False)
            self.menu = QMenu(self.tray_dummy); self.menu.addAction("Settings", self.show_settings)
            self.menu.addSeparator(); self.menu.addAction(f"Exit", self.emergency_exit)
            self.tray.setContextMenu(self.menu); self.tray.show()
            self.timer = QTimer(); self.timer.timeout.connect(self.tick); self.timer.start(16)
            self.settings_window = SettingsWindow(self); self.hide(); log_msg("V15 Started.")
        except Exception as e: log_msg(f"INIT ERROR: {e}\n{traceback.format_exc()}")

    def load_settings(self):
        self.zoom = float(self.settings_manager.value("zoom", 2.0))
        self.radius = int(self.settings_manager.value("radius", 150))
        self.opacity = float(self.settings_manager.value("opacity", 1.0))
        self.border_color = QColor(self.settings_manager.value("color", "#00FF00"))
        self.pointer_style = int(self.settings_manager.value("pointer_style", STYLE_NORMAL))
        self.spotlight_enabled = str(self.settings_manager.value("spotlight", "false")).lower() == "true"
        self.capture_mode = int(self.settings_manager.value("capture_mode", CAP_RECORD))
        keys = self.settings_manager.value("activation_keys", [VK_ALT, VK_MBUTTON])
        if isinstance(keys, str): keys = [int(keys)]
        try: self.activation_keys = [int(k) for k in keys if int(k) != VK_CONTROL]
        except: self.activation_keys = [VK_ALT, VK_MBUTTON]
        if not self.activation_keys: self.activation_keys = [VK_ALT]

    def save_settings(self):
        self.settings_manager.setValue("zoom", self.zoom); self.settings_manager.setValue("radius", self.radius); self.settings_manager.setValue("opacity", self.opacity); self.settings_manager.setValue("color", self.border_color.name()); self.settings_manager.setValue("pointer_style", self.pointer_style); self.settings_manager.setValue("spotlight", self.spotlight_enabled); self.settings_manager.setValue("capture_mode", self.capture_mode); self.settings_manager.setValue("activation_keys", self.activation_keys)

    def update_window_size(self):
        if self.spotlight_enabled:
            s = QGuiApplication.primaryScreen().geometry(); self.setFixedSize(s.width(), s.height()); self.move(0, 0)
        else: self.setFixedSize(int(self.radius*2+100), int(self.radius*2+100))
        self.setWindowOpacity(self.opacity)

    def apply_capture_flags(self):
        try:
            hwnd = self.winId().__int__()
            flag = WDA_EXCLUDEFROMCAPTURE if self.capture_mode == CAP_STEALTH else WDA_NONE
            ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, flag)
        except: pass

    def update_tray(self, active):
        pix = QPixmap(32, 32); pix.fill(Qt.GlobalColor.transparent); p = QPainter(pix)
        p.setBrush(QBrush(QColor("#2ecc71") if active else QColor("#e74c3c"))); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(4, 4, 24, 24); p.end(); self.tray.setIcon(QIcon(pix))

    def show_settings(self): self.settings_window.refresh_key_ui(); self.settings_window.show(); self.settings_window.raise_(); self.settings_window.activateWindow()
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
                    self.hide(); QApplication.processEvents(); time.sleep(0.02); self._cache = QGuiApplication.primaryScreen().grabWindow(0)
                self.update_window_size(); self.show(); self.raise_()
            if self.pointer_style != STYLE_NORMAL: self.toggle_global_cursor(state)
            if not state: self.hide(); self._cache = None

    def emergency_exit(self): restore_cursors(); QApplication.instance().quit()

    def tick(self):
        try:
            is_down = any(bool(GetAsyncKeyState(int(key)) & 0x8000) for key in self.activation_keys)
            self.set_active(is_down)
            c_p = bool(GetAsyncKeyState(VK_C) & 0x8000)
            if c_p and not self._last_c:
                self.pointer_style = (self.pointer_style + 1) % 4; self.save_settings(); self.force_cursor_update()
                for i in range(4):
                    b = self.settings_window.style_group.button(i)
                    if b: b.setChecked(i == self.pointer_style)
            self._last_c = c_p
            sl_p = bool(GetAsyncKeyState(VK_SLASH) & 0x8000)
            if sl_p and not self._last_slash:
                self.spotlight_enabled = not self.spotlight_enabled; self.save_settings(); self.update_window_size(); self.settings_window.spotlight_cb.setChecked(self.spotlight_enabled)
            self._last_slash = sl_p
            if not self._is_active: return
            if bool(GetAsyncKeyState(VK_UP) & 0x8000): self.zoom = min(15.0, self.zoom + 0.05)
            if bool(GetAsyncKeyState(VK_DOWN) & 0x8000): self.zoom = max(1.1, self.zoom - 0.05)
            if bool(GetAsyncKeyState(VK_RIGHT) & 0x8000): self.radius = min(600, self.radius + 3); self.update_window_size()
            if bool(GetAsyncKeyState(VK_LEFT) & 0x8000): self.radius = max(50, self.radius - 3); self.update_window_size()
            if bool(GetAsyncKeyState(VK_COMMA) & 0x8000): self.opacity = max(0.1, self.opacity - 0.02); self.setWindowOpacity(self.opacity)
            if bool(GetAsyncKeyState(VK_PERIOD) & 0x8000): self.opacity = min(1.0, self.opacity + 0.02); self.setWindowOpacity(self.opacity)
            pos = QCursor.pos(); screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
            if not self.spotlight_enabled: self.move(pos.x() - self.width() // 2, pos.y() - self.height() // 2)
            if screen:
                s_rect = screen.geometry(); cw, ch = int((self.radius * 2) / self.zoom), int((self.radius * 2) / self.zoom)
                ideal_rect = QRect(pos.x() - cw // 2, pos.y() - ch // 2, cw, ch)
                if self.capture_mode == CAP_RECORD and self._cache:
                    canvas = QPixmap(cw, ch); canvas.fill(Qt.GlobalColor.black); p_c = QPainter(canvas)
                    p_c.drawPixmap(QRect(0, 0, cw, ch), self._cache, ideal_rect.translated(-s_rect.x(), -s_rect.y()))
                    p_c.end(); self.pix = canvas
                else: self.pix = screen.grabWindow(0, pos.x() - cw // 2, pos.y() - ch // 2, cw, ch)
                self.update()
        except Exception as e: log_msg(f"TICK ERROR: {e}\n{traceback.format_exc()}")

    def paintEvent(self, event):
        if not self._is_active or self.pix is None: return
        try:
            p = QPainter(self); p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
            pos = QCursor.pos()
            if self.spotlight_enabled: p.fillRect(self.rect(), QColor(0, 0, 0, 180)); center = QPointF(float(pos.x()), float(pos.y()))
            else: center = QPointF(self.width()/2.0, self.height()/2.0)
            path = QPainterPath(); path.addEllipse(center, float(self.radius), float(self.radius))
            if self.spotlight_enabled: p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear); p.drawPath(path); p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setClipPath(path)
            if not self.spotlight_enabled: p.fillRect(self.rect(), QColor(0, 0, 0, int(self.opacity * 255)))
            
            # TRIP MODE SPIRAL LOGIC
            if self.capture_mode == CAP_TRIP:
                p.save(); p.translate(center); p.rotate(2)
                p.drawPixmap(QRect(-self.radius, -self.radius, self.radius*2, self.radius*2), self.pix)
                p.setBrush(QBrush(QColor(0, 0, 0, 15))); p.setPen(Qt.PenStyle.NoPen); p.drawEllipse(QPointF(0,0), float(self.radius), float(self.radius))
                p.restore()
            else: p.drawPixmap(QRectF(center.x()-self.radius, center.y()-self.radius, self.radius*2, self.radius*2).toRect(), self.pix)
            
            p.setClipping(False); p.setPen(QPen(self.border_color, 5)); p.drawEllipse(center, float(self.radius), float(self.radius))
            if self.pointer_style == STYLE_LASER:
                p.setBrush(QBrush(QColor(255, 0, 0, 200))); p.setPen(QPen(QColor(255, 255, 255, 150), 2))
                p.drawEllipse(center, 5, 5); p.setPen(QPen(QColor(255, 0, 0, 100), 10)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(center, 8, 8)
            elif self.pointer_style == STYLE_CROSSHAIR:
                p.setPen(QPen(self.border_color, 2)); l = 20; p.drawLine(QPointF(center.x() - l, center.y()), QPointF(center.x() + l, center.y())); p.drawLine(QPointF(center.x(), center.y() - l), QPointF(center.x(), center.y() + l)); p.drawEllipse(center, 10, 10)
        except Exception as e: log_msg(f"PAINT ERROR: {e}")

if __name__ == "__main__":
    restore_cursors(); app = QApplication(sys.argv); shared_mem = QSharedMemory(APP_ID)
    if not shared_mem.create(1): sys.exit(0)
    app.setQuitOnLastWindowClosed(False); app.aboutToQuit.connect(restore_cursors)
    try: m = Magnifier(); sys.exit(app.exec())
    except Exception as e: log_msg(f"FATAL ERROR: {e}"); restore_cursors()
