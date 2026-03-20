import sys
import time
from collections import deque

import serial
import serial.tools.list_ports

from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QFrame, QMessageBox
)



class LedIndicator(QFrame):
    """Green ON / Red OFF box."""
    def __init__(self):
        super().__init__()
        self.setFixedSize(46, 32)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(2)
        self._on = False
        self.set_on(False)

    def set_on(self, on: bool):
        self._on = on
        if on:
            self.setStyleSheet("background-color: #2ecc71;")
        else:
            self.setStyleSheet("background-color: #e74c3c;")
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.GlobalColor.white)
        p.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "ON" if self._on else "OFF")
        p.end()


class PlotBox(QWidget):
    """Simple scrolling plot for X and Y (0..1023)."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 260)
        self.x_hist = deque(maxlen=300)
        self.y_hist = deque(maxlen=300)

    def push(self, x: int, y: int):
        self.x_hist.append(x)
        self.y_hist.append(y)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Border
        p.setPen(QPen(Qt.GlobalColor.black, 2))
        p.setBrush(QBrush(Qt.GlobalColor.white))
        p.drawRect(self.rect().adjusted(1, 1, -1, -1))

        # Empty text
        if len(self.x_hist) < 2:
            p.setPen(Qt.GlobalColor.black)
            p.setFont(QFont("Arial", 14))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Data Visualization")
            p.end()
            return

        # Plot area
        r = self.rect().adjusted(12, 12, -12, -12)
        w = r.width()
        h = r.height()

        def ymap(v: int) -> float:
            v = max(0, min(1023, v))
            return r.top() + (1.0 - v / 1023.0) * h

        n = len(self.x_hist)
        if n < 2:
            p.end()
            return

        step = w / (n - 1)

        # X curve
        p.setPen(QPen(Qt.GlobalColor.darkBlue, 2))
        prev = None
        for i, v in enumerate(self.x_hist):
            pt = QPointF(r.left() + i * step, ymap(v))
            if prev is not None:
                p.drawLine(prev, pt)
            prev = pt

        # Y curve
        p.setPen(QPen(Qt.GlobalColor.darkGreen, 2))
        prev = None
        for i, v in enumerate(self.y_hist):
            pt = QPointF(r.left() + i * step, ymap(v))
            if prev is not None:
                p.drawLine(prev, pt)
            prev = pt

        p.end()


class ButtonMapping(QWidget):
    """Cross mapping + highlight direction."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(320, 260)
        self.dir = "CENTER"  # UP / DOWN / LEFT / RIGHT / CENTER

    def set_dir(self, d: str):
        self.dir = d
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        p.setPen(Qt.GlobalColor.black)
        p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        p.drawText(QRectF(0, 0, self.width(), 40), Qt.AlignmentFlag.AlignCenter, "Button Mapping")

        cx = self.width() / 2
        cy = self.height() / 2 + 10
        size = 70
        thick = 55

        rect_up = QRectF(cx - thick / 2, cy - size - thick / 2, thick, size)
        rect_down = QRectF(cx - thick / 2, cy + thick / 2, thick, size)
        rect_left = QRectF(cx - size - thick / 2, cy - thick / 2, size, thick)
        rect_right = QRectF(cx + thick / 2, cy - thick / 2, size, thick)
        rect_center = QRectF(cx - thick / 2, cy - thick / 2, thick, thick)

        def draw_rect(r: QRectF, active: bool):
            p.setPen(QPen(Qt.GlobalColor.darkGray, 2))
            p.setBrush(QBrush(Qt.GlobalColor.lightGray if active else Qt.GlobalColor.white))
            p.drawRect(r)

        draw_rect(rect_up, self.dir == "UP")
        draw_rect(rect_down, self.dir == "DOWN")
        draw_rect(rect_left, self.dir == "LEFT")
        draw_rect(rect_right, self.dir == "RIGHT")
        draw_rect(rect_center, self.dir == "CENTER")

        p.end()


# ------------------ Main GUI ------------------

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAB TASK 4 - Joystick GUI")

        self.ser = None          # Serial port obyekti. Başlanğıcda port açıq deyil.
        self.running = False     # Proqramın test rejimi işləyir ya yox.
        self.last_ts = None      # Son gələn datanın vaxtını saxlayır (sample rate hesablamaq üçün).
        self.hz = 0.0            # Serialdan gələn məlumatın tezliyi (Hz).

        # Top controls
        self.portBox = QComboBox() #dropdown
        self.refreshBtn = QPushButton("Refresh Ports")
        self.startStopBtn = QPushButton("Start/Stop Test")
        self.led = LedIndicator()

        top = QHBoxLayout() #Horizontal layout yaradır Widget-lər yan-yana düzüləcək
        top.addWidget(QLabel("Port:")) # Sadə "Port:" yazısı əlavə edir.
        top.addWidget(self.portBox, 1)
        top.addWidget(self.refreshBtn)
        top.addStretch(1)
        top.addWidget(self.startStopBtn)
        top.addWidget(self.led)

        # Main panels
        self.plot = PlotBox()
        self.mapping = ButtonMapping()

        mainRow = QHBoxLayout()
        mainRow.addWidget(self.plot, 3) #Plot panelini əlavə edir.
        mainRow.addSpacing(20)
        mainRow.addWidget(self.mapping, 2)

        # Bottom area
        dataTitle = QLabel("Data")
        dataTitle.setFont(QFont("Arial", 11, QFont.Weight.Bold))

        self.xText = QLabel("X: Voltage Level")
        self.yText = QLabel("Y: Voltage Level")
        self.rateText = QLabel("Sample Rate: ---- Hz")
        self.btnText = QLabel("Button: released")

        bottomGrid = QGridLayout()
        bottomGrid.addWidget(self.xText, 0, 0)
        bottomGrid.addWidget(self.rateText, 0, 1, alignment=Qt.AlignmentFlag.AlignRight)
        bottomGrid.addWidget(self.yText, 1, 0)
        bottomGrid.addWidget(self.btnText, 1, 1, alignment=Qt.AlignmentFlag.AlignRight)

        bottom = QVBoxLayout()
        bottom.addWidget(dataTitle)
        bottom.addLayout(bottomGrid)

        # Root layout
        root = QVBoxLayout()
        root.addLayout(top)
        root.addSpacing(10)
        root.addLayout(mainRow)
        root.addSpacing(10)
        root.addLayout(bottom)
        self.setLayout(root)

        # Timer
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.tick)

        # Signals
        self.refreshBtn.clicked.connect(self.refresh_ports)
        self.startStopBtn.clicked.connect(self.toggle_run)

        self.refresh_ports()
        self.led.set_on(False)

    def refresh_ports(self):
        self.portBox.clear() #COM portları tapır

        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            self.portBox.addItem(f"{p.device} - {p.description}", p.device) #Tapılan portları siyahıya əlavə edir

        if self.portBox.count() == 0:
            self.portBox.addItem("No ports found", None)

    def toggle_run(self):
        if not self.running:
            port = self.portBox.currentData()
            if not port:
                QMessageBox.warning(self, "No Port", "No valid COM port selected.")
                return

            try:
                self.ser = serial.Serial(port, 9600, timeout=0.1) #Serial portu açır
                time.sleep(0.2)
            except Exception as e:
                QMessageBox.critical(self, "Connect failed", str(e)) #Xəta mesajı göstərir.
                self.ser = None
                return

            self.running = True # LED yanır
            self.led.set_on(True) 
            self.startStopBtn.setText("Stop Test") #Düymə yazısı dəyişir
            self.last_ts = time.time()
            self.timer.start() 

        else:
            self.stop_serial()

    def stop_serial(self):
        self.timer.stop()
        self.running = False
        self.led.set_on(False)
        self.startStopBtn.setText("Start/Stop Test")

        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass

        self.ser = None
        self.rateText.setText("Sample Rate: ---- Hz")
        self.mapping.set_dir("CENTER")

    def tick(self):
        if not self.ser:
            return

        try:
            line = self.ser.readline().decode(errors="ignore").strip() #Serialdan bir sətir oxuyur b'520,480,1\r\n'
            if not line:
                return

            parts = line.split(",")
            if len(parts) != 3:
                return

            x = int(parts[0])
            y = int(parts[1])
            pressed = int(parts[2])  # 1 pressed, 0 released

            # Sample rate
            now = time.time()
            dt = now - (self.last_ts if self.last_ts else now)
            self.last_ts = now


            if dt > 0:
                self.hz = 0.9 * self.hz + 0.5 * (1.0 / dt) if self.hz else (1.0 / dt)
                self.rateText.setText(f"Sample Rate: {self.hz:.1f} Hz")

            # Voltage
            vx = x * 5.0 / 1023.0
            vy = y * 5.0 / 1023.0

            self.xText.setText(f"X: {vx:.2f} V  ({x})")
            self.yText.setText(f"Y: {vy:.2f} V  ({y})")
            self.btnText.setText("Button: PRESSED" if pressed == 1 else "Button: released")

            # Plot update
            self.plot.push(x, y)

            # Direction mapping
            dx = x - 512
            dy = y - 512
            dead = 70
            direction = "CENTER"

            if abs(dx) > dead or abs(dy) > dead:
                if abs(dx) > abs(dy):
                    direction = "RIGHT" if dx > 0 else "LEFT"
                else:
                    direction = "UP" if dy < 0 else "DOWN"

            self.mapping.set_dir(direction)

        except Exception:
            self.stop_serial()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(920, 560)
    w.show()
    sys.exit(app.exec())
