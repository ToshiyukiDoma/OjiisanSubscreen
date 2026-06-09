import sys, json
import cv2
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QEvent, QPropertyAnimation, QParallelAnimationGroup
from PySide6.QtGui import QPixmap, QColor, QPainter, QImage
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QComboBox, QGraphicsOpacityEffect

try:
    import vgamepad as vg
    GAMEPAD = True
except Exception:
    GAMEPAD = False

BUTTON_MAP = {}
if GAMEPAD:
    BUTTON_MAP = {
        "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
        "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
        "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
        "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
        "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
        "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        "BACK": vg.XUSB_BUTTON.XUSB_GAMEPAD_BACK,
        "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
        "LS": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB,
        "RS": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB,
        "UP": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP,
        "DOWN": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN,
        "LEFT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT,
        "RIGHT": vg.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT
    }

class Btn(QLabel):
    def __init__(self, main_win, parent_widget, cfg, sx, sy, overlay_img_name="pressed.png", asset_dir="ui"):
        super().__init__(parent_widget)
        self.main_win = main_win
        self.cfg = cfg
        self.overlay = False
        self.overlay_pixmap = None
        
        img = Path(asset_dir) / cfg["image"]
        if img.exists():
            pm = QPixmap(str(img))
            self.setPixmap(pm)
            self.setScaledContents(True)
            self.resize(max(1, int(pm.width() * sx)), max(1, int(pm.height() * sy)))
        else:
            self.setText(cfg.get("controller_button", "BTN"))
            self.setStyleSheet("background:#333;color:white;border:1px solid white;")
            self.resize(100, 100)
            
        self.move(int(cfg["x"] * sx), int(cfg["y"] * sy))

        overlay_path = Path(asset_dir) / overlay_img_name
        if overlay_path.exists():
            self.overlay_pixmap = QPixmap(str(overlay_path)).scaled(
                self.size(), Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )

    def mousePressEvent(self, e):
        self.overlay = True
        self.update()
        if "controller_button" in self.cfg:
            self.main_win.press_btn(self.cfg["controller_button"])
        QTimer.singleShot(100, self.release_vis)

    def release_vis(self):
        self.overlay = False
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.overlay:
            qp = QPainter(self)
            if self.overlay_pixmap:
                qp.drawPixmap(0, 0, self.overlay_pixmap)
            else:
                qp.fillRect(self.rect(), QColor(255, 0, 0, 76))

class Win(QWidget):
    def __init__(self):
        super().__init__()
        
        try:
            self.config = json.loads(Path("config.json").read_text(encoding="utf8"))
        except Exception:
            self.config = {}

        screens = QApplication.screens()
        idx = max(0, self.config.get("monitor", 1) - 1)
        if idx >= len(screens): idx = 0
        geo = screens[idx].geometry()
        self.setGeometry(geo)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

        # 1. Main background label
        self.bg = QLabel(self)
        self.bg.setGeometry(self.rect())

        # 2. Dim Overlay for Concentration Mode
        self.dim_overlay = QWidget(self)
        self.dim_overlay.setGeometry(self.rect())
        self.dim_overlay.setStyleSheet("background-color: black;")
        self.dim_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.dim_opacity_effect = QGraphicsOpacityEffect()
        self.dim_opacity_effect.setOpacity(0.0)
        self.dim_overlay.setGraphicsEffect(self.dim_opacity_effect)

        # 3. Concentration Icon
        self.conc_icon = QLabel(self)
        conc_cfg = self.config.get("concentration_mode", {})
        rw = self.config.get("reference_width", 1920)
        rh = self.config.get("reference_height", 1080)
        sx = self.width() / rw
        sy = self.height() / rh

        img_path = Path("ui") / conc_cfg.get("image", "concentration.png")
        if img_path.exists():
            pm = QPixmap(str(img_path))
            self.conc_icon.setPixmap(pm)
            self.conc_icon.setScaledContents(True)
            self.conc_icon.resize(int(pm.width() * sx), int(pm.height() * sy))
        else:
            self.conc_icon.setText("CONCENTRATION MODE")
            self.conc_icon.setStyleSheet("color:white; font-size:32px;")
            self.conc_icon.adjustSize()
            
        cx = int(conc_cfg.get("x", 800) * sx)
        cy = int(conc_cfg.get("y", 400) * sy)
        self.conc_icon.move(cx, cy)
        self.conc_icon.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.conc_icon_opacity = QGraphicsOpacityEffect()
        self.conc_icon_opacity.setOpacity(0.0)
        self.conc_icon.setGraphicsEffect(self.conc_icon_opacity)

        # 4. UI Container (Holds all buttons and dropdowns so they can fade out together)
        self.ui_container = QWidget(self)
        self.ui_container.setGeometry(self.rect())
        self.ui_opacity_effect = QGraphicsOpacityEffect()
        self.ui_opacity_effect.setOpacity(1.0)
        self.ui_container.setGraphicsEffect(self.ui_opacity_effect)

        # OpenCV Video setup
        self.video_cap = None
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self.update_video_frame)

        self.backgrounds = []
        self.background_names = []

        bg_dir = Path(self.config.get("background_directory", "backgrounds"))
        if not bg_dir.exists():
            bg_dir = Path("backgrounds")

        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.mp4", "*.webm"):
            for f in sorted(bg_dir.glob(ext)):
                self.backgrounds.append(f)
                self.background_names.append(f.stem)

        self.bg_index = 0
        self.load_background()

        # Dropdown UI
        self.bg_dropdown = QComboBox(self.ui_container)
        self.bg_dropdown.addItems(self.background_names)
        self.bg_dropdown.move(20, 20)
        self.bg_dropdown.resize(500, 80)
        self.bg_dropdown.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.bg_dropdown.setStyleSheet("""
        QComboBox {
            background-color: rgba(0,0,0,220);
            color: white;
            border: 3px solid white;
            border-radius: 10px;
            padding-left: 15px;
            font-size: 28px;
            font-weight: bold;
        }
        QComboBox QAbstractItemView {
            background-color: rgba(15, 15, 15, 240);
            color: white;
            border: 2px solid white;
            selection-background-color: rgba(255, 0, 0, 150);
            font-size: 24px;
        }
        QScrollBar:vertical {
            background-color: rgba(30, 30, 30, 200);
            width: 30px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background-color: rgba(120, 120, 120, 255);
            min-height: 40px;
            border-radius: 6px;
            margin: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: rgba(180, 180, 180, 255);
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: none;
            height: 0px;
        }
        """)
        self.bg_dropdown.currentIndexChanged.connect(self.change_background)

        self.gamepad = None
        if GAMEPAD:
            try:
                self.gamepad = vg.VX360Gamepad()
            except Exception:
                pass

        overlay_img = self.config.get("pressed_overlay_image", "pressed.png")

        # Load buttons into the ui_container
        for b in self.config.get("main_buttons", []):
            Btn(self, self.ui_container, b, sx, sy, overlay_img).show()

        self.extra_buttons = []
        for b in self.config.get("extra_buttons", []):
            btn = Btn(self, self.ui_container, b, sx, sy, overlay_img)
            btn.show()
            self.extra_buttons.append(btn)

        self.extras_visible = not self.config.get("extras_hidden_on_startup", True)
        self.update_extras()

        default_toggle = {"image": "system_toggle.png", "x": 1650, "y": 100, "controller_button": "UP"}
        toggle_cfg = self.config.get("toggle_button", default_toggle)
        self.toggle_btn = Btn(self, self.ui_container, toggle_cfg, sx, sy, overlay_img)
        self.toggle_btn.mousePressEvent = lambda e: self.toggle_extras()
        self.toggle_btn.show()

        # Concentration Mode Animation Setup
        self.in_concentration_mode = False
        self.anim_group = QParallelAnimationGroup()
        
        self.anim_ui = QPropertyAnimation(self.ui_opacity_effect, b"opacity")
        self.anim_dim = QPropertyAnimation(self.dim_opacity_effect, b"opacity")
        self.anim_icon = QPropertyAnimation(self.conc_icon_opacity, b"opacity")
        
        self.anim_ui.setDuration(1000)
        self.anim_dim.setDuration(1000)
        self.anim_icon.setDuration(1000)
        
        self.anim_group.addAnimation(self.anim_ui)
        self.anim_group.addAnimation(self.anim_dim)
        self.anim_group.addAnimation(self.anim_icon)

        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.enter_concentration_mode)
        
        # Install global event filter to catch all touches
        QApplication.instance().installEventFilter(self)

        self.showFullScreen()
        self.reset_idle_timer()

    def eventFilter(self, watched, event):
        t = event.type()
        # Reset timer on any mouse move, click, or touch
        if t in (QEvent.MouseMove, QEvent.MouseButtonPress, QEvent.TouchBegin, QEvent.TouchUpdate):
            self.reset_idle_timer()
            
            # Wake up if asleep
            if self.in_concentration_mode:
                self.exit_concentration_mode()
                # Consume the initial click so it doesn't accidentally trigger a button underneath
                if t in (QEvent.MouseButtonPress, QEvent.TouchBegin):
                    return True
                    
        return super().eventFilter(watched, event)

    def reset_idle_timer(self):
        conc_cfg = self.config.get("concentration_mode", {})
        if not conc_cfg.get("enabled", True):
            return
            
        timeout_ms = int(conc_cfg.get("timeout_seconds", 60) * 1000)
        self.idle_timer.start(timeout_ms)

    def enter_concentration_mode(self):
        if self.in_concentration_mode: return
        self.in_concentration_mode = True
        
        self.anim_group.stop()
        self.anim_ui.setEndValue(0.0)
        self.anim_dim.setEndValue(self.config.get("concentration_mode", {}).get("dim_opacity", 0.5))
        self.anim_icon.setEndValue(1.0)
        self.anim_group.start()

    def exit_concentration_mode(self):
        if not self.in_concentration_mode: return
        self.in_concentration_mode = False
        
        self.anim_group.stop()
        self.anim_ui.setEndValue(1.0)
        self.anim_dim.setEndValue(0.0)
        self.anim_icon.setEndValue(0.0)
        self.anim_group.start()

    def update_extras(self):
        for b in self.extra_buttons:
            b.setVisible(self.extras_visible)

    def toggle_extras(self):
        self.extras_visible = not self.extras_visible
        self.update_extras()

    def change_background(self, index):
        self.bg_index = index
        self.load_background()

    def load_background(self):
        self.video_timer.stop()
        if self.video_cap is not None:
            self.video_cap.release()
            self.video_cap = None

        if not self.backgrounds:
            self.bg.setStyleSheet("background:black;")
            return

        file = self.backgrounds[self.bg_index]
        ext = file.suffix.lower()

        if ext in (".mp4", ".webm"):
            self.video_cap = cv2.VideoCapture(str(file.resolve()))
            fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            interval = int(1000 / fps) if fps > 0 else 33 
            self.video_timer.start(interval)
        else:
            self.bg.setPixmap(QPixmap(str(file)).scaled(
                self.size(),
                Qt.IgnoreAspectRatio,
                Qt.SmoothTransformation
            ))

    def update_video_frame(self):
        if self.video_cap is None or not self.video_cap.isOpened():
            return

        ret, frame = self.video_cap.read()
        
        if not ret:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_cap.read()
            if not ret:
                return

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        bytes_per_line = ch * w

        qimg = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.size(),
            Qt.IgnoreAspectRatio,
            Qt.SmoothTransformation
        )
        
        self.bg.setPixmap(pixmap)

    def press_btn(self, name):
        if not self.gamepad or name not in BUTTON_MAP:
            return
        btn = BUTTON_MAP[name]
        self.gamepad.press_button(button=btn)
        self.gamepad.update()
        QTimer.singleShot(60, lambda: self.release_btn(btn))

    def release_btn(self, btn):
        self.gamepad.release_button(button=btn)
        self.gamepad.update()

    def closeEvent(self, event):
        self.video_timer.stop()
        if self.video_cap is not None:
            self.video_cap.release()
        super().closeEvent(event)

app = QApplication(sys.argv)
w = Win()
sys.exit(app.exec())