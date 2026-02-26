import sys
import os
import json
import subprocess
import shutil
import time
from threading import Thread

import requests
from PyQt5 import QtWidgets, QtGui, QtCore
import serial
import serial.tools.list_ports

try:
    import ctypes
except ImportError:
    ctypes = None


GITHUB_API_RELEASES = "https://api.github.com/repos/BruceDevices/firmware/releases"
APP_DIR = os.path.join(os.path.expanduser("~"), "BruceLauncher")
SETTINGS_PATH = os.path.join(APP_DIR, "settings.json")


DEVICE_PROFILES = []


def get_resource_path(name: str) -> str:
    """простая штука чтоб картинки и прочие файлы искались рядом с exe а не где попало"""
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, name)


class AppSettings:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True)
        # тут короче стоят такие значения по умолчанию типо
        self.firmware_dir = os.path.join(APP_DIR, "firmware")
        self.backup_dir = os.path.join(APP_DIR, "backups")
        self.send_tone_on_connect = True
        self.ask_firmware_path_each_time = False
        self.ask_backup_path_each_time = False
        self.chip_type = "esp32"  # esp32, esp32s3
        self.graphic_progress = True
        self.language = "ru"
        self._load()

    def _load(self):
        if not os.path.isfile(SETTINGS_PATH):
            return
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        self.firmware_dir = data.get("firmware_dir", self.firmware_dir)
        self.backup_dir = data.get("backup_dir", self.backup_dir)
        self.send_tone_on_connect = bool(data.get("send_tone_on_connect", self.send_tone_on_connect))
        self.ask_firmware_path_each_time = bool(data.get("ask_firmware_path_each_time", self.ask_firmware_path_each_time))
        self.ask_backup_path_each_time = bool(data.get("ask_backup_path_each_time", self.ask_backup_path_each_time))
        self.chip_type = data.get("chip_type", self.chip_type)
        self.graphic_progress = bool(data.get("graphic_progress", self.graphic_progress))
        self.language = data.get("language", self.language)

    def save(self):
        data = {
            "firmware_dir": self.firmware_dir,
            "backup_dir": self.backup_dir,
            "send_tone_on_connect": self.send_tone_on_connect,
            "ask_firmware_path_each_time": self.ask_firmware_path_each_time,
            "ask_backup_path_each_time": self.ask_backup_path_each_time,
            "chip_type": self.chip_type,
            "graphic_progress": self.graphic_progress,
            "language": self.language,
        }
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class BruceStyle:
    """тут чутка намутили палитру и стили чтоб было как на bruce.computer но не прям один в один"""

    BG_DARK = "#050608"
    BG_CARD = "#0d1117"
    ACCENT = "#00ff99"
    ACCENT_SOFT = "#00cc7a"
    TEXT_MAIN = "#e6edf3"
    TEXT_MUTED = "#8b949e"
    BORDER = "#161b22"

    @staticmethod
    def apply(app: QtWidgets.QApplication):
        palette = app.palette()
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(BruceStyle.BG_DARK))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(BruceStyle.TEXT_MAIN))
        palette.setColor(QtGui.QPalette.Base, QtGui.QColor(BruceStyle.BG_CARD))
        palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(BruceStyle.BG_DARK))
        palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(BruceStyle.BG_CARD))
        palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(BruceStyle.TEXT_MAIN))
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(BruceStyle.TEXT_MAIN))
        palette.setColor(QtGui.QPalette.Button, QtGui.QColor(BruceStyle.BG_CARD))
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(BruceStyle.TEXT_MAIN))
        palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(BruceStyle.ACCENT_SOFT))
        palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(BruceStyle.BG_DARK))
        app.setPalette(palette)

        app.setStyleSheet(f"""
            QWidget {{
                background-color: {BruceStyle.BG_DARK};
                color: {BruceStyle.TEXT_MAIN};
                font-family: "Segoe UI", "Inter", "Roboto", sans-serif;
                font-size: 11pt;
            }}

            QMainWindow {{
                background-color: {BruceStyle.BG_DARK};
                border: none;
            }}

            QWidget#RootCentral {{
                background-color: {BruceStyle.BG_DARK};
                background-image: url(bruce.png);
                background-position: center;
                background-repeat: no-repeat;
                background-origin: content;
            }}

            QDialog {{
                background-color: {BruceStyle.BG_DARK};
                border: none;
            }}

            QGroupBox {{
                border: 1px solid {BruceStyle.BORDER};
                border-top: 2px solid {BruceStyle.ACCENT_SOFT};
                border-radius: 10px;
                margin-top: 18px;
                padding: 14px;
                background-color: {BruceStyle.BG_CARD};
            }}

            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
                color: {BruceStyle.TEXT_MUTED};
                font-weight: 600;
                letter-spacing: 0.5px;
            }}

            QLabel#TitleLabel {{
                font-size: 22pt;
                font-weight: 800;
            }}

            QLabel#SubtitleLabel {{
                color: {BruceStyle.TEXT_MUTED};
                font-size: 10pt;
            }}

            /* Яркое, но читаемое выделение элементов */
            QTreeView::item:selected,
            QListView::item:selected,
            QTableView::item:selected,
            QAbstractItemView::item:selected {{
                background-color: {BruceStyle.ACCENT_SOFT};
                color: {BruceStyle.BG_DARK};
            }}

            QComboBox QAbstractItemView::item:selected {{
                background-color: {BruceStyle.ACCENT_SOFT};
                color: {BruceStyle.BG_DARK};
            }}

            QLineEdit:focus,
            QComboBox:focus,
            QPlainTextEdit:focus {{
                border: 1px solid {BruceStyle.ACCENT_SOFT};
            }}

            QPushButton {{
                background-color: {BruceStyle.BG_CARD};
                border-radius: 6px;
                border: 1px solid {BruceStyle.BORDER};
                padding: 6px 12px;
                color: {BruceStyle.TEXT_MAIN};
            }}

            QPushButton:hover {{
                border-color: {BruceStyle.ACCENT_SOFT};
                background-color: #0f151f;
            }}

            QPushButton:pressed {{
                background-color: #050b10;
            }}

            QPushButton[accent="true"] {{
                background-color: {BruceStyle.ACCENT};
                color: {BruceStyle.BG_DARK};
                font-weight: 600;
            }}

            QPushButton[accent="true"]:hover {{
                background-color: {BruceStyle.ACCENT_SOFT};
            }}

            QComboBox, QLineEdit {{
                background-color: {BruceStyle.BG_CARD};
                border-radius: 4px;
                border: 1px solid {BruceStyle.BORDER};
                padding: 4px 6px;
            }}

            QPlainTextEdit {{
                background-color: #050608;
                border-radius: 4px;
                border: 1px solid {BruceStyle.BORDER};
                font-family: "JetBrains Mono", "Consolas", monospace;
                font-size: 9pt;
            }}

            QMenuBar {{
                background-color: #050608;
                color: {BruceStyle.TEXT_MAIN};
            }}

            QMenuBar::item:selected {{
                background-color: #0f151f;
            }}

            QMenu {{
                background-color: #050608;
                color: {BruceStyle.TEXT_MAIN};
                border: 1px solid {BruceStyle.BORDER};
            }}

            QMenu::item:selected {{
                background-color: #0f151f;
            }}

            QScrollBar:vertical {{
                background: {BruceStyle.BG_DARK};
                width: 8px;
                margin: 0px;
            }}

            QScrollBar::handle:vertical {{
                background: {BruceStyle.BORDER};
                border-radius: 4px;
            }}
        """)


class SerialConsole(QtWidgets.QDialog):
    def __init__(self, parent=None, send_tone_on_connect: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Bruce Serial Console")
        # убрал эту дурацкую кнопку с вопросиком вверху она тут вообще не нужна
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.resize(700, 400)

        self.port_box = QtWidgets.QComboBox()
        self.baud_box = QtWidgets.QComboBox()
        self.baud_box.addItems(["115200", "921600"])
        self.refresh_ports()

        self.open_btn = QtWidgets.QPushButton("Открыть")
        self.close_btn = QtWidgets.QPushButton("Закрыть")
        self.close_btn.setEnabled(False)

        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)

        # это типа верхняя панель тут порт скорость и всякие кнопки
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Порт:"))
        top.addWidget(self.port_box)
        top.addWidget(QtWidgets.QLabel("Скорость:"))
        top.addWidget(self.baud_box)
        top.addWidget(self.open_btn)
        top.addWidget(self.close_btn)

        # Нижняя панель ввода команды
        self.input_edit = QtWidgets.QLineEdit()
        self.input_edit.setPlaceholderText("Команда для отправки на устройство...")
        self.send_btn = QtWidgets.QPushButton("Отправить")
        self.send_btn.setEnabled(False)

        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(self.input_edit, 1)
        bottom.addWidget(self.send_btn)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(self.text, 1)
        layout.addLayout(bottom)
        self.setLayout(layout)

        self.serial = None
        self._reader_thread = None
        self._stop = False
        self.send_tone_on_connect = send_tone_on_connect

        self.open_btn.clicked.connect(self.open_port)
        self.close_btn.clicked.connect(self.close_port)
        self.send_btn.clicked.connect(self.send_command)
        self.input_edit.returnPressed.connect(self.send_command)

    def refresh_ports(self):
        self.port_box.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_box.addItem(f"{p.device} - {p.description}", p.device)

    def open_port(self):
        device = self.port_box.currentData()
        if not device:
            QtWidgets.QMessageBox.warning(self, "Serial", "Не найден доступный COM порт.")
            return
        baud = int(self.baud_box.currentText())
        try:
            self.serial = serial.Serial(device, baudrate=baud, timeout=0.1)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Serial", f"Ошибка открытия порта:\n{e}")
            return

        # Автоматически отправляем команду tone при подключении, если включено в настройках
        if self.send_tone_on_connect:
            try:
                self.serial.write(b"tone\n")
            except Exception:
                pass

        self._stop = False
        self._reader_thread = Thread(target=self.read_loop, daemon=True)
        self._reader_thread.start()
        self.open_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.send_btn.setEnabled(True)

    def read_loop(self):
        while not self._stop and self.serial and self.serial.is_open:
            try:
                line = self.serial.readline()
                if line:
                    text = line.decode(errors="replace").rstrip("\r\n")
                    if text:
                        QtCore.QMetaObject.invokeMethod(
                            self.text,
                            "appendPlainText",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, text),
                        )
            except Exception:
                break
            time.sleep(0.01)

    def close_port(self):
        self._stop = True
        if self.serial:
            try:
                self.serial.close()
            except Exception:
                pass
            self.serial = None
        self.open_btn.setEnabled(True)
        self.close_btn.setEnabled(False)
        self.send_btn.setEnabled(False)

    def send_command(self):
        if not self.serial or not self.serial.is_open:
            return
        cmd = self.input_edit.text()
        if not cmd:
            return
        # если в конце нет перевода строки то дописываем сами а то порт иногда тупит без него
        if not cmd.endswith("\n"):
            cmd += "\n"
        try:
            self.serial.write(cmd.encode(errors="ignore"))
            self.input_edit.clear()
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Serial", "Не удалось отправить команду.")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.close_port()
        super().closeEvent(event)


class BackupModeDialog(QtWidgets.QDialog):
    """окно где выбираем как бэкап делать сейчас честно только полный образ потом может еще что нибудь прикрутим"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Режим бэкапа")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.mode = "full"

        layout = QtWidgets.QVBoxLayout()

        desc = QtWidgets.QLabel(
            "Сейчас поддерживается только полный образ флеш‑памяти."
        )
        layout.addWidget(desc)

        self.rb_full = QtWidgets.QRadioButton("Полный образ (вся флеш‑память)")
        self.rb_full.setChecked(True)
        layout.addWidget(self.rb_full)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout.addWidget(btn_box)

        btn_box.accepted.connect(self.on_accept)
        btn_box.rejected.connect(self.reject)

        self.setLayout(layout)

    def on_accept(self):
        self.mode = "full"
        self.accept()


class LoadingSpinner(QtWidgets.QWidget):
    """просто такой крутящийся кружок загрузки без всяких изысков но смотрится норм"""

    def __init__(self, parent=None, size: int = 64):
        super().__init__(parent)
        self._angle = 0
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._on_timeout)
        self._timer.start(80)
        self._size = size
        self.setFixedSize(size, size)

    def _on_timeout(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)
        pen = QtGui.QPen(QtGui.QColor(BruceStyle.ACCENT))
        pen.setWidth(3)
        painter.setPen(pen)

        # тут рисуется такая дуга почти полный круг и она крутится короче как спиннер
        start_angle = int(self._angle * 16)
        span_angle = int(270 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        painter.end()


class SplashScreen(QtWidgets.QDialog):
    """короткий экранчик при старте чтоб логотип мелькнул и выглядело как будто все по взрослому"""

    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Dialog
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        size = 260
        self.resize(size, size)

        # тут по тихому ставим окно почти по центру монитора чтоб не улетело в угол
        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(
                geo.center().x() - size // 2,
                geo.center().y() - size // 2,
            )

        outer = QtWidgets.QFrame()
        outer.setObjectName("SplashOuter")
        outer_layout = QtWidgets.QVBoxLayout()
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(10)
        outer.setLayout(outer_layout)

        ring = QtWidgets.QFrame()
        ring.setObjectName("SplashRing")
        ring.setFixedSize(200, 200)

        ring_layout = QtWidgets.QVBoxLayout()
        ring_layout.setContentsMargins(16, 16, 16, 16)
        ring_layout.setSpacing(8)
        ring_layout.setAlignment(QtCore.Qt.AlignCenter)
        ring.setLayout(ring_layout)

        logo = QtWidgets.QLabel()
        logo.setAlignment(QtCore.Qt.AlignCenter)
        logo_path = get_resource_path("wLogo.png")
        if os.path.isfile(logo_path):
            pix = QtGui.QPixmap(logo_path)
            if not pix.isNull():
                logo.setPixmap(
                    pix.scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                )
        logo.setObjectName("SplashLogo")

        spinner = LoadingSpinner(self, size=72)

        ring_layout.addWidget(logo)
        ring_layout.addWidget(spinner, alignment=QtCore.Qt.AlignCenter)

        title = QtWidgets.QLabel("Bruce Launcher")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setObjectName("TitleLabel")

        outer_layout.addWidget(ring, alignment=QtCore.Qt.AlignCenter)
        outer_layout.addWidget(title, alignment=QtCore.Qt.AlignCenter)

        root = QtWidgets.QVBoxLayout()
        root.addWidget(outer)
        self.setLayout(root)


class ProgressDialog(QtWidgets.QDialog):
    """окошко где крутится загрузка и снизу меняется текст прогресса чтоб было понятно что оно не зависло"""

    def __init__(self, parent: QtWidgets.QWidget, title: str, initial_text: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Dialog
            | QtCore.Qt.WindowStaysOnTopHint
        )
        self.setModal(True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        size = 280
        self.resize(size, size)

        screen = QtWidgets.QApplication.primaryScreen()
        if screen:
            geo = screen.geometry()
            self.move(
                geo.center().x() - size // 2,
                geo.center().y() - size // 2,
            )

        outer = QtWidgets.QFrame()
        outer.setObjectName("SplashOuter")
        outer_layout = QtWidgets.QVBoxLayout()
        outer_layout.setContentsMargins(20, 20, 20, 20)
        outer_layout.setSpacing(10)
        outer.setLayout(outer_layout)

        ring = QtWidgets.QFrame()
        ring.setObjectName("SplashRing")
        ring.setFixedSize(200, 200)

        ring_layout = QtWidgets.QVBoxLayout()
        ring_layout.setContentsMargins(16, 16, 16, 16)
        ring_layout.setSpacing(8)
        ring_layout.setAlignment(QtCore.Qt.AlignCenter)
        ring.setLayout(ring_layout)

        logo = QtWidgets.QLabel()
        logo.setAlignment(QtCore.Qt.AlignCenter)
        logo_path = get_resource_path("wLogo.png")
        if os.path.isfile(logo_path):
            pix = QtGui.QPixmap(logo_path)
            if not pix.isNull():
                logo.setPixmap(
                    pix.scaled(56, 56, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                )
        logo.setObjectName("SplashLogo")

        self.spinner = LoadingSpinner(self, size=64)

        self.success_icon = QtWidgets.QLabel("✓")
        self.success_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.success_icon.setFixedSize(64, 64)
        self.success_icon.setStyleSheet(
            f"background-color: {BruceStyle.ACCENT}; color: {BruceStyle.BG_DARK};"
            "border-radius: 32px; font-size: 28pt; font-weight: 700;"
        )
        self.success_icon.hide()

        ring_layout.addWidget(logo)
        ring_layout.addWidget(self.spinner, alignment=QtCore.Qt.AlignCenter)
        ring_layout.addWidget(self.success_icon, alignment=QtCore.Qt.AlignCenter)

        self.msg_label = QtWidgets.QLabel(initial_text)
        self.msg_label.setObjectName("SubtitleLabel")
        self.msg_label.setAlignment(QtCore.Qt.AlignCenter)

        outer_layout.addWidget(ring, alignment=QtCore.Qt.AlignCenter)
        outer_layout.addWidget(self.msg_label, alignment=QtCore.Qt.AlignCenter)

        root = QtWidgets.QVBoxLayout()
        root.addWidget(outer)
        self.setLayout(root)

    @QtCore.pyqtSlot(str)
    def set_message(self, text: str):
        self.msg_label.setText(text)

    @QtCore.pyqtSlot(str)
    def set_success(self, text: str = ""):
        self.spinner.hide()
        self.success_icon.show()
        if text:
            self.msg_label.setText(text)
        QtCore.QTimer.singleShot(800, self.accept)


class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, settings: AppSettings):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self._settings = settings

        fw_edit = QtWidgets.QLineEdit(settings.firmware_dir)
        fw_btn = QtWidgets.QPushButton("…")
        fw_btn.setFixedWidth(32)

        bk_edit = QtWidgets.QLineEdit(settings.backup_dir)
        bk_btn = QtWidgets.QPushButton("…")
        bk_btn.setFixedWidth(32)

        tone_chk = QtWidgets.QCheckBox("Отправлять команду 'tone' при подключении к Serial")
        tone_chk.setChecked(settings.send_tone_on_connect)

        ask_fw_chk = QtWidgets.QCheckBox("Каждый раз выбирать файл для прошивки вручную")
        ask_fw_chk.setChecked(settings.ask_firmware_path_each_time)
        ask_bk_chk = QtWidgets.QCheckBox("Каждый раз выбирать файл для бэкапа вручную")
        ask_bk_chk.setChecked(settings.ask_backup_path_each_time)

        gfx_prog_chk = QtWidgets.QCheckBox("Графическое окно прогресса (сплэш при прошивке/бэкапе)")
        gfx_prog_chk.setChecked(settings.graphic_progress)

        chip_label = QtWidgets.QLabel("Чип ESP:")
        chip_combo = QtWidgets.QComboBox()
        chip_combo.addItem("ESP32", "esp32")
        chip_combo.addItem("ESP32-S3", "esp32s3")
        # установить текущее значение
        idx = chip_combo.findData(settings.chip_type)
        if idx >= 0:
            chip_combo.setCurrentIndex(idx)

        fw_row = QtWidgets.QHBoxLayout()
        fw_row.addWidget(fw_edit, 1)
        fw_row.addWidget(fw_btn)

        bk_row = QtWidgets.QHBoxLayout()
        bk_row.addWidget(bk_edit, 1)
        bk_row.addWidget(bk_btn)

        form = QtWidgets.QFormLayout()
        form.addRow("Папка для временных прошивок:", fw_row)
        form.addRow("Папка для бэкапов:", bk_row)
        form.addRow("", tone_chk)
        form.addRow("", ask_fw_chk)
        form.addRow("", ask_bk_chk)
        form.addRow(chip_label, chip_combo)
        form.addRow("", gfx_prog_chk)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(btn_box)
        self.setLayout(layout)

        def choose_dir(edit: QtWidgets.QLineEdit):
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Выбор папки", edit.text() or APP_DIR
            )
            if path:
                edit.setText(path)

        fw_btn.clicked.connect(lambda: choose_dir(fw_edit))
        bk_btn.clicked.connect(lambda: choose_dir(bk_edit))
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        self._fw_edit = fw_edit
        self._bk_edit = bk_edit
        self._tone_chk = tone_chk
        self._ask_fw_chk = ask_fw_chk
        self._ask_bk_chk = ask_bk_chk
        self._chip_combo = chip_combo
        self._gfx_prog_chk = gfx_prog_chk

    def apply_changes(self) -> AppSettings:
        self._settings.firmware_dir = self._fw_edit.text().strip() or self._settings.firmware_dir
        self._settings.backup_dir = self._bk_edit.text().strip() or self._settings.backup_dir
        self._settings.send_tone_on_connect = self._tone_chk.isChecked()
        self._settings.ask_firmware_path_each_time = self._ask_fw_chk.isChecked()
        self._settings.ask_backup_path_each_time = self._ask_bk_chk.isChecked()
        self._settings.chip_type = self._chip_combo.currentData()
        self._settings.graphic_progress = self._gfx_prog_chk.isChecked()
        return self._settings


class AboutDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("О программе Bruce Launcher")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.resize(420, 260)

        layout = QtWidgets.QVBoxLayout()

        top = QtWidgets.QHBoxLayout()

        logo_label = QtWidgets.QLabel()
        logo_label.setFixedSize(72, 72)
        logo_path = get_resource_path("wLogo.png")
        if os.path.isfile(logo_path):
            pix = QtGui.QPixmap(logo_path)
            if not pix.isNull():
                logo_label.setPixmap(pix.scaled(72, 72, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        top.addWidget(logo_label)

        text_box = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("Bruce Launcher")
        title.setObjectName("TitleLabel")
        subtitle = QtWidgets.QLabel("Разработано ErkinKraft\nЛицензия: MIT")
        subtitle.setObjectName("SubtitleLabel")

        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        top.addLayout(text_box)
        top.addStretch(1)

        layout.addLayout(top)

        info = QtWidgets.QLabel()
        info.setTextFormat(QtCore.Qt.RichText)
        info.setText(
            "Удобный лаунчер для прошивки устройств Bruce ESP32,<br>"
            "поддерживающий установку релизов, бэкапы и Serial консоль.<br>"
            "Официальный сайт прошивки: "
            "<a href=\"https://bruce.computer/\">bruce.computer</a>"
        )
        info.setOpenExternalLinks(True)
        layout.addWidget(info)

        github_btn = QtWidgets.QPushButton("GitHub: ErkinKraft")
        github_btn.setProperty("accent", True)
        github_btn.setMinimumHeight(34)
        github_btn.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl("https://github.com/ErkinKraft"))
        )
        layout.addWidget(github_btn, alignment=QtCore.Qt.AlignLeft)

        btn_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        btn_box.rejected.connect(self.reject)
        btn_box.accepted.connect(self.accept)
        # Кнопка Close по умолчанию на правой стороне
        layout.addWidget(btn_box)

        self.setLayout(layout)


class FlashConfirmDialog(QtWidgets.QDialog):
    """диалог перед тем как шить плату тут решаем стирать ли флеш и еще раз спрашиваем точно ли ты уверен"""

    def __init__(self, parent, release_info: dict, port: str):
        super().__init__(parent)
        self.setWindowTitle("Подтверждение прошивки")
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        self.erase_flash = False

        tag = release_info.get("tag") or release_info.get("name") or "unknown"

        layout = QtWidgets.QVBoxLayout()

        text = QtWidgets.QLabel(
            f"Будет прошита прошивка <b>{tag}</b> на устройство <b>{port}</b>"
        )
        text.setTextFormat(QtCore.Qt.RichText)
        layout.addWidget(text)

        self.erase_chk = QtWidgets.QCheckBox("Полностью стереть флеш перед прошивкой (erase_flash)")
        layout.addWidget(self.erase_chk)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        layout.addWidget(btn_box)

        btn_box.accepted.connect(self.on_accept)
        btn_box.rejected.connect(self.reject)

        self.setLayout(layout)

    def on_accept(self):
        if self.erase_chk.isChecked():
            res = QtWidgets.QMessageBox.question(
                self,
                "Стирание данных",
                "Внимание! При включённом erase_flash ВСЕ данные на устройстве будут стёрты.\n"
                "Ты точно хочешь продолжить?",
            )
            if res != QtWidgets.QMessageBox.Yes:
                self.reject()
                return
            self.erase_flash = True
        self.accept()


class BruceLauncher(QtWidgets.QMainWindow):
    # тут сигнал чтоб из разных потоков можно было писать в лог не ломая гуи
    log_signal = QtCore.pyqtSignal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Bruce Launcher")
        self.resize(900, 600)

        self.settings = AppSettings()

        icon = QtGui.QIcon()
        self.setWindowIcon(icon)

        central = QtWidgets.QWidget()
        central.setObjectName("RootCentral")
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        central.setLayout(main_layout)

        header = self._build_header()
        main_layout.addLayout(header)

        content_layout = QtWidgets.QHBoxLayout()
        main_layout.addLayout(content_layout, 1)

        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        content_layout.addLayout(left, 2)
        content_layout.addLayout(right, 1)

        self.releases_combo = QtWidgets.QComboBox()
        self.refresh_releases_btn = QtWidgets.QPushButton("Обновить список")
        self.flash_latest_btn = QtWidgets.QPushButton("Последний релиз")
        self.flash_latest_btn.setProperty("accent", True)
        self.flash_beta_btn = QtWidgets.QPushButton("Последняя бета")
        self.flash_specific_btn = QtWidgets.QPushButton("Выбранная версия")

        fw_group = QtWidgets.QGroupBox("Прошивка")
        fw_l = QtWidgets.QVBoxLayout()
        fw_group.setLayout(fw_l)

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Версия:"))
        row1.addWidget(self.releases_combo, 1)
        row1.addWidget(self.refresh_releases_btn)
        fw_l.addLayout(row1)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(self.flash_latest_btn)
        row2.addWidget(self.flash_beta_btn)
        row2.addWidget(self.flash_specific_btn)
        fw_l.addLayout(row2)

        left.addWidget(fw_group)

        backup_group = QtWidgets.QGroupBox("Бэкап")
        b_l = QtWidgets.QVBoxLayout()
        backup_group.setLayout(b_l)

        self.backup_btn = QtWidgets.QPushButton("Создать бэкап")
        self.restore_btn = QtWidgets.QPushButton("Восстановить из бэкапа")
        b_l.addWidget(self.backup_btn)
        b_l.addWidget(self.restore_btn)

        left.addWidget(backup_group)

        tools_group = QtWidgets.QGroupBox("Инструменты")
        t_l = QtWidgets.QVBoxLayout()
        tools_group.setLayout(t_l)

        self.serial_btn = QtWidgets.QPushButton("Открыть Serial консоль")
        t_l.addWidget(self.serial_btn)

        left.addWidget(tools_group)
        left.addStretch(1)

        log_group = QtWidgets.QGroupBox("Лог")
        log_l = QtWidgets.QVBoxLayout()
        log_group.setLayout(log_l)

        self.log_view = QtWidgets.QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_l.addWidget(self.log_view)

        right.addWidget(log_group, 1)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Готово")

        # связываем этот сигнал логов с функцией которая уже в интерфейсе все рисует
        self.log_signal.connect(self._append_log)

        # Меню
        menubar = self.menuBar()
        self.menu_app = menubar.addMenu("")
        self.menu_lang = menubar.addMenu("")

        self.act_settings = QtWidgets.QAction(self)
        self.act_about = QtWidgets.QAction(self)
        self.menu_app.addAction(self.act_settings)
        self.menu_app.addSeparator()
        self.menu_app.addAction(self.act_about)

        self.act_lang_ru = QtWidgets.QAction(self)
        self.act_lang_en = QtWidgets.QAction(self)
        self.act_lang_ru.setCheckable(True)
        self.act_lang_en.setCheckable(True)
        lang_group = QtWidgets.QActionGroup(self)
        lang_group.setExclusive(True)
        lang_group.addAction(self.act_lang_ru)
        lang_group.addAction(self.act_lang_en)
        self.menu_lang.addAction(self.act_lang_ru)
        self.menu_lang.addAction(self.act_lang_en)

        self.act_settings.triggered.connect(self.open_settings)
        self.act_about.triggered.connect(self.show_about)
        self.act_lang_ru.triggered.connect(lambda: self.change_language("ru"))
        self.act_lang_en.triggered.connect(lambda: self.change_language("en"))

        self.refresh_releases_btn.clicked.connect(self.load_releases)
        self.flash_latest_btn.clicked.connect(lambda: self.flash("latest"))
        self.flash_beta_btn.clicked.connect(lambda: self.flash("beta"))
        self.flash_specific_btn.clicked.connect(lambda: self.flash("selected"))
        self.backup_btn.clicked.connect(self.create_backup)
        self.restore_btn.clicked.connect(self.restore_backup)
        self.serial_btn.clicked.connect(self.open_serial)

        self.releases = []
        self.load_releases()

        # пробуем включить темную рамку окна в винде если она вообще это подтянет
        self._enable_windows_dark_titlebar()

        # делаем маленькую анимацию появления чтоб не выскакивало резко в лицо
        self.setWindowOpacity(0.0)
        fade = QtCore.QPropertyAnimation(self, b"windowOpacity")
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._fade_anim = fade
        self._fade_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

        # добавил легкие тени под блоками чисто для красоты чтоб выглядело поживее
        for group in (fw_group, backup_group, tools_group, log_group):
            shadow = QtWidgets.QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(24)
            shadow.setOffset(0, 0)
            shadow.setColor(QtGui.QColor(0, 0, 0, 180))
            group.setGraphicsEffect(shadow)

        # в самом конце подтягиваем язык из настроек и раскладываем все надписи
        self._current_language = self.settings.language or "ru"
        self.apply_language()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        # тут по тихому чистим временные файлы прошивок когда лаунчер закрывается чтоб мусор не копился
        if os.path.isdir(self.settings.firmware_dir):
            try:
                shutil.rmtree(self.settings.firmware_dir, ignore_errors=True)
            except Exception:
                pass
        super().closeEvent(event)

    # выбор самого устройства тут убрали теперь чип настраиваем руками в настройках esp32 или esp32s3

    def _enable_windows_dark_titlebar(self):
        """пытаемся включить темную рамку окна в windows десять и выше если повезет"""
        if sys.platform != "win32" or ctypes is None:
            return
        try:
            hwnd = int(self.winId())
            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            value = ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.wintypes.HWND(hwnd),
                ctypes.wintypes.DWORD(DWMWA_USE_IMMERSIVE_DARK_MODE),
                ctypes.byref(value),
                ctypes.sizeof(value),
            )
        except Exception:
            # Если не получилось — просто игнорируем
            pass

    def change_language(self, lang: str):
        """сюда прилетает выбор языка из меню и мы просто сохраняем и перерисовываем подписи"""
        if lang not in ("ru", "en"):
            return
        if getattr(self, "_current_language", "ru") == lang:
            return
        self._current_language = lang
        self.settings.language = lang
        self.settings.save()
        self.apply_language()

    def apply_language(self):
        """тут просто руками меняем все подписи в зависимости от выбранного языка"""
        lang = self._current_language

        if lang == "en":
            self.setWindowTitle("Bruce Launcher")

            # меню
            self.menu_app.setTitle("Application")
            self.menu_lang.setTitle("Language")
            self.act_settings.setText("Settings…")
            self.act_about.setText("About…")
            self.act_lang_ru.setText("Русский")
            self.act_lang_en.setText("English")

            # заголовок и сабтайтл
            # здесь специально тексты жёстко, чтобы не городить отдельные словари
            for w in self.findChildren(QtWidgets.QLabel, "TitleLabel"):
                if w.text().strip().lower().startswith("bruce launcher"):
                    w.setText("Bruce Launcher")
            for w in self.findChildren(QtWidgets.QLabel, "SubtitleLabel"):
                txt = w.text().strip()
                if "Предаторный лаунчер" in txt or "launcher" in txt.lower():
                    w.setText("Simple flashing launcher for Bruce ESP32 devices")

            # группы
            for g in self.findChildren(QtWidgets.QGroupBox):
                if g.title() == "Прошивка":
                    g.setTitle("Firmware")
                elif g.title() == "Бэкап":
                    g.setTitle("Backup")
                elif g.title() == "Инструменты":
                    g.setTitle("Tools")
                elif g.title() == "Лог":
                    g.setTitle("Log")

            # кнопки
            self.refresh_releases_btn.setText("Refresh list")
            self.flash_latest_btn.setText("Latest release")
            self.flash_beta_btn.setText("Latest beta")
            self.flash_specific_btn.setText("Selected version")
            self.backup_btn.setText("Create backup")
            self.restore_btn.setText("Restore from backup")
            self.serial_btn.setText("Open Serial console")

            self.status_bar.showMessage("Ready")

        else:
            self.setWindowTitle("Bruce Launcher")

            self.menu_app.setTitle("Приложение")
            self.menu_lang.setTitle("Language")
            self.act_settings.setText("Настройки…")
            self.act_about.setText("О программе…")
            self.act_lang_ru.setText("Русский")
            self.act_lang_en.setText("English")

            for w in self.findChildren(QtWidgets.QLabel, "TitleLabel"):
                if w.text().strip().lower().startswith("bruce launcher"):
                    w.setText("Bruce Launcher")
            for w in self.findChildren(QtWidgets.QLabel, "SubtitleLabel"):
                txt = w.text().strip()
                if "Simple flashing launcher" in txt or "launcher" in txt.lower():
                    w.setText("Предаторный лаунчер прошивки Bruce для ESP32 устройств")

            for g in self.findChildren(QtWidgets.QGroupBox):
                if g.title() == "Firmware":
                    g.setTitle("Прошивка")
                elif g.title() == "Backup":
                    g.setTitle("Бэкап")
                elif g.title() == "Tools":
                    g.setTitle("Инструменты")
                elif g.title() == "Log":
                    g.setTitle("Лог")

            self.refresh_releases_btn.setText("Обновить список")
            self.flash_latest_btn.setText("Последний релиз")
            self.flash_beta_btn.setText("Последняя бета")
            self.flash_specific_btn.setText("Выбранная версия")
            self.backup_btn.setText("Создать бэкап")
            self.restore_btn.setText("Восстановить из бэкапа")
            self.serial_btn.setText("Открыть Serial консоль")

            self.status_bar.showMessage("Готово")

        # галочки на выборе языка
        self.act_lang_ru.setChecked(lang == "ru")
        self.act_lang_en.setChecked(lang == "en")

    def _build_header(self) -> QtWidgets.QHBoxLayout:
        layout = QtWidgets.QHBoxLayout()

        title_box = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel("Bruce Launcher")
        title.setObjectName("TitleLabel")
        title_font = QtGui.QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QtWidgets.QLabel("Предаторный лаунчер прошивки Bruce для ESP32 устройств")
        subtitle.setObjectName("SubtitleLabel")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        layout.addLayout(title_box)
        layout.addStretch(1)

        links_box = QtWidgets.QVBoxLayout()
        def make_link(text: str, url: str) -> QtWidgets.QLabel:
            lbl = QtWidgets.QLabel(f'<a href="{url}">{text}</a>')
            lbl.setOpenExternalLinks(True)
            lbl.setStyleSheet(f"color: {BruceStyle.ACCENT};")
            return lbl

        links_box.addWidget(make_link("Website", "https://bruce.computer/"))
        links_box.addWidget(make_link("Wiki", "https://wiki.bruce.computer/"))
        links_box.addWidget(make_link("GitHub", "https://github.com/BruceDevices/firmware"))

        layout.addLayout(links_box)

        return layout

    def _append_log(self, msg: str):
        """эта штука крутится только в основном гуи потоке и просто дописывает текст в лог и в строку статуса"""
        self.log_view.appendPlainText(msg)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
        self.status_bar.showMessage(msg)

    def log(self, msg: str):
        """лог который можно дергать из любого потока он через сигнал сам долетит куда надо"""
        self.log_signal.emit(msg)

    def load_releases(self):
        self.log("Загрузка списка релизов из GitHub...")
        self.releases_combo.clear()
        self.releases = []
        try:
            resp = requests.get(GITHUB_API_RELEASES, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.log(f"Ошибка получения релизов: {e}")
            QtWidgets.QMessageBox.critical(self, "GitHub", f"Не удалось получить список релизов:\n{e}")
            return

        for rel in data:
            name = rel.get("name") or rel.get("tag_name")
            tag = rel.get("tag_name")
            prerelease = rel.get("prerelease", False)
            assets = rel.get("assets", [])
            self.releases.append({
                "name": name,
                "tag": tag,
                "prerelease": prerelease,
                "assets": assets,
            })
            label = f"{name} ({'beta' if prerelease else 'stable'})"
            self.releases_combo.addItem(label, tag)

        self.log(f"Загружено релизов: {len(self.releases)}")

    def _pick_release(self, kind: str):
        if not self.releases:
            QtWidgets.QMessageBox.warning(self, "Релизы", "Список релизов пуст. Обновите список.")
            return None

        if kind in ("latest", "beta"):
            stable_list = []
            prerelease_list = []
            beta_by_name_list = []

            for rel in self.releases:
                name = (rel.get("name") or "").lower()
                tag = (rel.get("tag") or "").lower()
                prerelease = bool(rel.get("prerelease", False))

                # В репозитории Bruce есть спец-тег lastRelease, который указывает на последний стабильный релиз,
                # но помечен как prerelease=True. Его нужно считать стабильным, а не бетой.
                is_last_release_alias = (tag == "lastrelease")

                if prerelease and not is_last_release_alias:
                    prerelease_list.append(rel)
                elif ("beta" in name) or ("beta" in tag):
                    beta_by_name_list.append(rel)
                else:
                    stable_list.append(rel)

            if kind == "latest":
                # последний стабильный релиз
                if stable_list:
                    return stable_list[0]
                # если по какой-то причине стабильных нет — берём первый из всех
                return self.releases[0]

            # kind == "beta"
            # 1) сначала строго prerelease (кроме lastRelease)
            if prerelease_list:
                return prerelease_list[0]
            # 2) если prerelease нет, пробуем "beta" в имени/теге
            if beta_by_name_list:
                return beta_by_name_list[0]
            QtWidgets.QMessageBox.information(self, "Бета", "Бета‑версий не найдено.")
            return None

        # kind == "selected"
        idx = self.releases_combo.currentIndex()
        if idx < 0 or idx >= len(self.releases):
            QtWidgets.QMessageBox.warning(self, "Релизы", "Выберите версию.")
            return None
        return self.releases[idx]

    def flash(self, kind: str):
        rel = self._pick_release(kind)
        if not rel:
            return

        # Явно показываем какой релиз выбран (чтобы было видно, beta это или stable)
        self.log(
            f"Выбран релиз: tag={rel.get('tag')} name={rel.get('name')} prerelease={rel.get('prerelease')}"
        )

        assets = rel.get("assets", [])
        if not assets:
            QtWidgets.QMessageBox.warning(self, "Прошивка", "В релизе нет файлов прошивки.")
            return

        # собираем тут список всех bin файлов из этого релиза
        bin_assets = [a for a in assets if (a.get("name") or "").lower().endswith(".bin")]
        if not bin_assets:
            QtWidgets.QMessageBox.warning(self, "Прошивка", "В релизе нет .bin файлов прошивки.")
            return

        # открываем окошко где уже руками выбираем какой именно bin под свое железо ставить
        items = [a.get("name") or "firmware.bin" for a in bin_assets]
        item, ok = QtWidgets.QInputDialog.getItem(
            self,
            "Выбор файла прошивки",
            "Выберите файл прошивки (.bin), подходящий вашему устройству:",
            items,
            0,
            False,
        )
        if not ok:
            return
        sel_idx = items.index(item)
        asset = bin_assets[sel_idx]

        url = asset.get("browser_download_url")
        if not url:
            QtWidgets.QMessageBox.warning(self, "Прошивка", "Не найден URL файла прошивки.")
            return

        os.makedirs(self.settings.firmware_dir, exist_ok=True)
        default_name = asset.get("name", "firmware.bin")

        if self.settings.ask_firmware_path_each_time:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Куда сохранить прошивку",
                os.path.join(self.settings.firmware_dir, default_name),
                "BIN files (*.bin)",
            )
            if not path:
                return
            local_path = path
        else:
            local_path = os.path.join(self.settings.firmware_dir, default_name)

        self.log(f"Скачивание прошивки {rel['tag']} ({asset.get('name', '')})...")

        try:
            with requests.get(url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
        except Exception as e:
            self.log(f"Ошибка скачивания: {e}")
            QtWidgets.QMessageBox.critical(self, "Скачивание", f"Не удалось скачать прошивку:\n{e}")
            return

        self.log(f"Прошивка сохранена: {local_path}")

        ports = list(serial.tools.list_ports.comports())
        if not ports:
            QtWidgets.QMessageBox.warning(self, "Прошивка", "ESP32 устройство не найдено (COM порт).")
            return

        items = [f"{p.device} - {p.description}" for p in ports]
        item, ok = QtWidgets.QInputDialog.getItem(self, "Выбор порта", "COM порт:", items, 0, False)
        if not ok:
            return
        sel_idx = items.index(item)
        port = ports[sel_idx].device

        # перед прошивкой еще раз выскакивает окно чтоб точно подтвердить и можно включить стирание флеша
        confirm = FlashConfirmDialog(self, rel, port)
        if confirm.exec_() != QtWidgets.QDialog.Accepted:
            return
        erase_flash = confirm.erase_flash
        self.log(f"Запуск прошивки на {port} (erase_flash={erase_flash})...")

        progress = None
        if self.settings.graphic_progress:
            progress = ProgressDialog(self, "Прошивка", "Подключение к устройству...")
            progress.show()

        Thread(
            target=self._run_esptool_flash,
            args=(port, local_path, erase_flash, progress),
            daemon=True,
        ).start()

    def _run_esptool_flash(self, port: str, path: str, erase_flash: bool, progress: "ProgressDialog | None"):
        chip = self.settings.chip_type
        base_cmd = [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            chip,
            "--port",
            port,
            "--baud",
            "921600",
        ]

        def run_cmd(args, message: str = ""):
            if progress is not None and message:
                try:
                    QtCore.QMetaObject.invokeMethod(
                        progress,
                        "set_message",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, message),
                    )
                except Exception:
                    pass
            self.log(" ".join(args))
            try:
                proc = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in proc.stdout:
                    self.log(line.rstrip("\n"))
                proc.wait()
                return proc.returncode
            except Exception as e:
                self.log(f"Ошибка запуска esptool: {e}")
                return -1

        # если юзер включил стирание флеша то сначала пробуем его почистить а уже потом шить
        if erase_flash:
            rc = run_cmd(base_cmd + ["erase_flash"], "Стирание флеша (erase_flash)...")
            if rc != 0:
                self.log("Стирание флеша завершилось с ошибкой, прошивка отменена.")
                if progress is not None:
                    try:
                        QtCore.QMetaObject.invokeMethod(
                            progress,
                            "set_message",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, "Ошибка стирания флеша."),
                        )
                    except Exception:
                        pass
                return

        # основная прошивка здесь без всяких фокусов просто пишем bin по адресу ноль
        rc = run_cmd(base_cmd + ["write_flash", "0x0", path], "Запись прошивки во флеш...")
        if rc == 0:
            self.log("Прошивка завершена успешно.")
            # если все ок то удаляем за собой файлик прошивки чтоб не валялся зря
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception:
                pass
            if progress is not None:
                try:
                    QtCore.QMetaObject.invokeMethod(
                        progress,
                        "set_success",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, "Прошивка завершена успешно."),
                    )
                except Exception:
                    pass
        else:
            self.log(f"Ошибка прошивки, код {rc}")
            if progress is not None:
                try:
                    QtCore.QMetaObject.invokeMethod(
                        progress,
                        "set_message",
                        QtCore.Qt.QueuedConnection,
                        QtCore.Q_ARG(str, f"Ошибка прошивки, код {rc}."),
                    )
                except Exception:
                    pass

    def create_backup(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            QtWidgets.QMessageBox.warning(self, "Бэкап", "ESP32 устройство не найдено (COM порт).")
            return

        items = [f"{p.device} - {p.description}" for p in ports]
        item, ok = QtWidgets.QInputDialog.getItem(self, "Выбор порта", "COM порт:", items, 0, False)
        if not ok:
            return
        sel_idx = items.index(item)
        port = ports[sel_idx].device

        save_dir = self.settings.backup_dir
        os.makedirs(save_dir, exist_ok=True)
        default_name = "bruce_backup.bin"

        if self.settings.ask_backup_path_each_time:
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self, "Сохранить бэкап", os.path.join(save_dir, default_name), "BIN files (*.bin)"
            )
            if not path:
                return
        else:
            path = os.path.join(save_dir, default_name)

        # размер флеша сначала пытаемся вытащить через esptool flash_id
        # если вдруг не смогли тогда просто берем по старинке 16мб
        flash_size = self._detect_flash_size(port) or (16 * 1024 * 1024)
        self.log(f"Создание ПОЛНОГО бэкапа с устройства {port} (объём {flash_size} байт)...")

        progress = None
        if self.settings.graphic_progress:
            progress = ProgressDialog(self, "Бэкап", "Чтение флеша устройства...")
            progress.show()

        Thread(
            target=self._run_esptool_backup,
            args=(port, flash_size, path, "0x0", progress),
            daemon=True,
        ).start()

    def _detect_flash_size(self, port: str):
        chip = self.settings.chip_type
        cmd = [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            chip,
            "--port",
            port,
            "--baud",
            "921600",
            "flash_id",
        ]
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        except Exception:
            return None

        # пример строки от esptool типо Detected flash size: 16MB
        for line in out.splitlines():
            line = line.strip()
            if "Detected flash size" in line and ":" in line:
                size_part = line.split(":", 1)[1].strip().upper()
                # варианты тут обычно 4mb 8mb 16mb 32mb и так далее
                if size_part.endswith("MB"):
                    try:
                        mb = int(size_part[:-2])
                        return mb * 1024 * 1024
                    except Exception:
                        return None
        return None

    def _run_esptool_backup(self, port: str, size: int, path: str, offset_hex: str = "0x0", progress: "ProgressDialog | None" = None):
        chip = self.settings.chip_type
        cmd = [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            chip,
            "--port",
            port,
            "--baud",
            "921600",
            "read-flash",
            offset_hex,
            str(size),
            path,
        ]
        self.log(" ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self.log(line.rstrip("\n"))
            proc.wait()
            if proc.returncode == 0:
                self.log("Бэкап успешно создан.")
                if progress is not None:
                    try:
                        QtCore.QMetaObject.invokeMethod(
                            progress,
                            "set_success",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, "Бэкап успешно создан."),
                        )
                    except Exception:
                        pass
                # после удачного бэкапа сразу открываем папку где он лежит чтоб долго не искать
                try:
                    folder = os.path.dirname(path)
                    if sys.platform == "win32":
                        os.startfile(folder)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", folder])
                    else:
                        subprocess.Popen(["xdg-open", folder])
                except Exception:
                    pass
            else:
                self.log(f"Ошибка бэкапа, код {proc.returncode}")
                if progress is not None:
                    try:
                        QtCore.QMetaObject.invokeMethod(
                            progress,
                            "set_message",
                            QtCore.Qt.QueuedConnection,
                            QtCore.Q_ARG(str, f"Ошибка бэкапа, код {proc.returncode}."),
                        )
                    except Exception:
                        pass
        except Exception as e:
            self.log(f"Ошибка запуска esptool: {e}")

    def restore_backup(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Выбрать файл бэкапа", "", "BIN files (*.bin)"
        )
        if not path:
            return

        ports = list(serial.tools.list_ports.comports())
        if not ports:
            QtWidgets.QMessageBox.warning(self, "Бэкап", "ESP32 устройство не найдено (COM порт).")
            return

        items = [f"{p.device} - {p.description}" for p in ports]
        item, ok = QtWidgets.QInputDialog.getItem(self, "Выбор порта", "COM порт:", items, 0, False)
        if not ok:
            return
        sel_idx = items.index(item)
        port = ports[sel_idx].device

        if QtWidgets.QMessageBox.question(
            self,
            "Подтверждение",
            f"Перезаписать флеш устройства {port} содержимым бэкапа?\nДействие нельзя отменить."
        ) != QtWidgets.QMessageBox.Yes:
            return

        self.log(f"Восстановление бэкапа на {port}...")
        Thread(target=self._run_esptool_restore, args=(port, path), daemon=True).start()

    def _run_esptool_restore(self, port: str, path: str):
        chip = self.settings.chip_type
        cmd = [
            sys.executable,
            "-m",
            "esptool",
            "--chip",
            chip,
            "--port",
            port,
            "--baud",
            "921600",
            "write_flash",
            "0x0",
            path,
        ]
        self.log(" ".join(cmd))
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self.log(line.rstrip("\n"))
            proc.wait()
            if proc.returncode == 0:
                self.log("Бэкап успешно восстановлен.")
            else:
                self.log(f"Ошибка восстановления, код {proc.returncode}")
        except Exception as e:
            self.log(f"Ошибка запуска esptool: {e}")

    def open_serial(self):
        dlg = SerialConsole(self, send_tone_on_connect=self.settings.send_tone_on_connect)
        dlg.refresh_ports()
        dlg.exec_()

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            self.settings = dlg.apply_changes()
            self.settings.save()
            self.log("Настройки сохранены.")

    def show_about(self):
        dlg = AboutDialog(self)
        dlg.exec_()


def main():
    app = QtWidgets.QApplication(sys.argv)
    BruceStyle.apply(app)

    # при старте на секунду показываем сплэш чтобы не казалось что прога тупо не запускается
    splash = SplashScreen()
    splash.show()
    QtWidgets.QApplication.processEvents()

    def start_main():
        win = BruceLauncher()
        win.show()
        splash.close()

    QtCore.QTimer.singleShot(1000, start_main)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

