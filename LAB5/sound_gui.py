import sys
import time
from collections import deque

import serial
import serial.tools.list_ports

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox,
    QTableWidget, QTableWidgetItem, QMessageBox
)

import pyqtgraph as pg


class SoundMonitorGUI(QWidget):
    """
    Reads UART lines from Arduino in CSV format: time_ms,soundValue
    Live-plots the soundValue, and stores ONLY points where soundValue > threshold.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LAB TASK 5 - Sound Monitor GUI")
        self.resize(1000, 650)

        # Serial
        self.ser = None

        # Live plot buffers (last ~10-20 seconds depending on sampling)
        self.t_buf = deque(maxlen=600)
        self.s_buf = deque(maxlen=600)

        # Stored exceed events: list of (time_ms, soundValue)
        self.exceed_events = []

        # ui hissesi
        main = QVBoxLayout()

        # yuxari kontrollar
        top = QHBoxLayout()

        self.portBox = QComboBox()
        self.refreshBtn = QPushButton("Refresh")
        self.connectBtn = QPushButton("Connect")
        self.statusLbl = QLabel("Disconnected")

        top.addWidget(QLabel("Port:"))
        top.addWidget(self.portBox)
        top.addWidget(self.refreshBtn)
        top.addWidget(self.connectBtn)
        top.addWidget(self.statusLbl, stretch=1)

        # Threshold control
        self.thresholdSpin = QSpinBox()
        self.thresholdSpin.setRange(0, 1023)
        self.thresholdSpin.setValue(100)  
        top.addWidget(QLabel("Threshold:"))
        top.addWidget(self.thresholdSpin)

        main.addLayout(top)

        # Current value row
        info = QHBoxLayout()
        self.currentLbl = QLabel("Current sound: -")
        self.exceedCountLbl = QLabel("Exceed events stored: 0")
        info.addWidget(self.currentLbl)
        info.addWidget(self.exceedCountLbl, stretch=1)
        main.addLayout(info)

        # Plot widget (engaging visualization)
        self.plot = pg.PlotWidget()
        self.plot.setLabel("left", "Sound (0-1023)")
        self.plot.setLabel("bottom", "Time (s)")
        self.plot.showGrid(x=True, y=True)
        self.curve = self.plot.plot([], [])
        # Threshold line
        self.th_line = pg.InfiniteLine(angle=0, movable=False)
        self.plot.addItem(self.th_line)
        main.addWidget(self.plot, stretch=1)

        # Table for exceed events (only saved values)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Time (ms)", "Sound value"])
        self.table.setColumnWidth(0, 180)
        self.table.setColumnWidth(1, 140)
        main.addWidget(self.table)

        # Bottom buttons
        bottom = QHBoxLayout()
        self.clearBtn = QPushButton("Clear exceed events")
        self.exportBtn = QPushButton("Export to CSV")
        bottom.addWidget(self.clearBtn)
        bottom.addWidget(self.exportBtn)
        bottom.addStretch(1)
        main.addLayout(bottom)

        self.setLayout(main)

        # ---------- Signals ----------
        self.refreshBtn.clicked.connect(self.refresh_ports)
        self.connectBtn.clicked.connect(self.toggle_connection)
        self.clearBtn.clicked.connect(self.clear_events)
        self.exportBtn.clicked.connect(self.export_csv)

        # ---------- Timer (non-blocking GUI loop) ----------
        self.timer = QTimer()
        self.timer.timeout.connect(self.tick)
        self.timer.start(20)

        self.refresh_ports()
        self.update_threshold_line()

        # Update threshold line if user changes threshold
        self.thresholdSpin.valueChanged.connect(self.update_threshold_line)

    def update_threshold_line(self):
        self.th_line.setValue(self.thresholdSpin.value())

    def refresh_ports(self):
        self.portBox.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.portBox.addItem(p.device)
        if self.portBox.count() == 0:
            self.portBox.addItem("No ports")

    def toggle_connection(self):
        # Disconnect
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None
            self.statusLbl.setText("Disconnected")
            self.connectBtn.setText("Connect")
            return

        # Connect
        port = self.portBox.currentText()
        if "No ports" in port:
            QMessageBox.warning(self, "No Port", "No serial ports found.")
            return

        try:
            self.ser = serial.Serial(port, 115200, timeout=0)
            self.ser.reset_input_buffer()
            self.statusLbl.setText(f"Connected: {port}")
            self.connectBtn.setText("Disconnect")
        except Exception as e:
            QMessageBox.critical(self, "Connect failed", str(e))
            self.ser = None

    def tick(self):
        # serial yoxdur?
        if not (self.ser and self.ser.is_open):
            return

        threshold = self.thresholdSpin.value()

        # butun linelari oxu without blocking
        while True:
            line = self.ser.readline()
            if not line:
                break

            try:
                s = line.decode(errors="ignore").strip()
                # expected: time_ms,soundValue
                parts = s.split(",")
                if len(parts) != 2:
                    continue

                t_ms = int(parts[0])
                sound = int(parts[1])

                # Update live buffers
                t_s = t_ms / 1000.0
                self.t_buf.append(t_s)
                self.s_buf.append(sound)

                self.currentLbl.setText(f"Current sound: {sound}   (t={t_ms} ms)")

                # Store only if exceeds threshold
                if sound > threshold:
                    self.exceed_events.append((t_ms, sound))
                    self.add_event_row(t_ms, sound)

            except Exception:
                continue

        # Update plot
        if len(self.t_buf) >= 2:
            self.curve.setData(list(self.t_buf), list(self.s_buf))

        self.exceedCountLbl.setText(f"Exceed events stored: {len(self.exceed_events)}")

    def add_event_row(self, t_ms, sound):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(str(t_ms)))
        self.table.setItem(r, 1, QTableWidgetItem(str(sound)))
        self.table.scrollToBottom()

    def clear_events(self):
        self.exceed_events.clear()
        self.table.setRowCount(0)
        self.exceedCountLbl.setText("Exceed events stored: 0")

    def export_csv(self):
        if not self.exceed_events:
            QMessageBox.information(self, "Nothing to export", "No exceed events recorded yet.")
            return

        filename = f"exceed_events_{int(time.time())}.csv"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("time_ms,sound_value\n")
            for t_ms, sound in self.exceed_events:
                f.write(f"{t_ms},{sound}\n")

        QMessageBox.information(self, "Exported", f"Saved to {filename}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = SoundMonitorGUI()
    w.show()
    sys.exit(app.exec())
