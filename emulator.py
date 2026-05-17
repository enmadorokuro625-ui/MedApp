import sys
import socket
import threading
import time
import random
import math
from collections import deque

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QRadioButton, QGroupBox, QSlider,
                             QTextEdit, QGridLayout)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg

# --------------------------------------------------------------
# Генераторы сигналов
# --------------------------------------------------------------
class SignalGenerator:
    def __init__(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val
        self.value = (min_val + max_val) // 2

    def update(self):
        raise NotImplementedError

    def set_limits(self, min_val, max_val):
        self.min_val = min_val
        self.max_val = max_val
        self.value = max(min_val, min(max_val, self.value))

class PulseGenerator(SignalGenerator):
    def __init__(self, min_val, max_val, bpm=75):
        super().__init__(min_val, max_val)
        self.bpm = bpm
        self.interval = 60.0 / bpm
        self.last_peak = time.time()
        self.peak_duration = 0.05

    def update(self):
        now = time.time()
        time_since_peak = now - self.last_peak
        if time_since_peak <= self.peak_duration:
            self.value = self.max_val
        else:
            t = time_since_peak - self.peak_duration
            if t < 0.2:
                decay = math.exp(-t * 20)
                self.value = self.min_val + (self.max_val - self.min_val) * decay
            else:
                self.value = self.min_val

        if time_since_peak >= self.interval:
            self.last_peak = now
        return int(self.value)

class EMGGenerator(SignalGenerator):
    def __init__(self, min_val, max_val):
        super().__init__(min_val, max_val)
        self.mid = (min_val + max_val) / 2
        self.amp = (max_val - min_val) / 2

    def update(self):
        noise = random.gauss(0, self.amp / 3)
        self.value = self.mid + noise
        self.value += math.sin(time.time() * 0.5) * (self.amp / 4)
        self.value = max(self.min_val, min(self.max_val, self.value))
        return int(self.value)

    def set_limits(self, min_val, max_val):
        super().set_limits(min_val, max_val)
        self.mid = (min_val + max_val) / 2
        self.amp = (max_val - min_val) / 2

class EEGGenerator(SignalGenerator):
    def __init__(self, min_val, max_val, freq_hz=10):
        super().__init__(min_val, max_val)
        self.freq = freq_hz
        self.start_time = time.time()
        self.amp = (max_val - min_val) / 2
        self.mid = (min_val + max_val) / 2

    def update(self):
        t = time.time() - self.start_time
        self.value = self.mid + self.amp * math.sin(2 * math.pi * self.freq * t)
        self.value += random.uniform(-10, 10)
        self.value = max(self.min_val, min(self.max_val, self.value))
        return int(self.value)

    def set_limits(self, min_val, max_val):
        super().set_limits(min_val, max_val)
        self.amp = (max_val - min_val) / 2
        self.mid = (min_val + max_val) / 2

class GSRGenerator(SignalGenerator):
    def __init__(self, min_val, max_val):
        super().__init__(min_val, max_val)
        self.step = (max_val - min_val) / 200

    def update(self):
        self.value += random.uniform(-self.step, self.step)
        if random.random() < 0.01:
            self.value += random.uniform(-self.step*5, self.step*5)
        self.value = max(self.min_val, min(self.max_val, self.value))
        return int(self.value)

    def set_limits(self, min_val, max_val):
        super().set_limits(min_val, max_val)
        self.step = (max_val - min_val) / 200

# --------------------------------------------------------------
# Главное окно приложения
# --------------------------------------------------------------
class ESPEmulatorApp(QMainWindow):
    update_plots_signal = pyqtSignal()
    log_signal = pyqtSignal(str)

    SCENARIOS = {
        "Спокойное":       (1500, 3500, 200, 800, 1500, 2500, 1000, 2000, 50),
        "Стресс":          (2000, 3900, 400, 1500, 1200, 2200, 2000, 3800, 75),
        "Физ. нагрузка":   (2400, 4095, 500, 2000, 1000, 2100, 1800, 3500, 70),
        "Медитация":       (1200, 2800, 100, 400, 1800, 3000, 500, 1200, 30),
        "Концентрация":    (1500, 3000, 300, 1000, 2000, 3800, 800, 1500, 85),
        "Усталость":       (1600, 3200, 150, 600, 1300, 2000, 1500, 2800, 20),
        "Паника":          (2800, 4095, 600, 2000, 1000, 1800, 2500, 4095, 90),
        "Сонливость":      (1300, 2500, 100, 350, 1000, 1800, 1200, 2200, 15),
    }

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Эмулятор ESP32 - Медицинские датчики")
        self.setGeometry(100, 100, 1300, 900)

        # Состояние
        self.running = False
        self.send_thread = None
        self.recv_thread = None
        self.stop_receiver = False

        # Границы каналов
        self.pulse_min, self.pulse_max = 1500, 3500
        self.emg_min,   self.emg_max   = 200, 800
        self.eeg_min,   self.eeg_max   = 1500, 2500
        self.gsr_min,   self.gsr_max   = 1000, 2000

        # Генераторы и текущие значения
        self.generators = {}
        self.current_values = {"pulse": 0, "emg": 0, "eeg": 0, "gsr": 0}

        # История для графиков (200 точек)
        self.history_len = 200
        self.histories = {ch: deque(maxlen=self.history_len) for ch in ["pulse", "emg", "eeg", "gsr"]}

        # Медицинские показатели
        self.bpm = 0.0
        self.stress = 50
        self.muscle = 0
        self.mental_load = 0   # новый показатель
        self.last_peak_time = 0
        self.emg_buffer = deque(maxlen=50)
        self.eeg_buffer = deque(maxlen=50)   # для расчёта mental load

        # Создаём интерфейс
        self.init_ui()
        self.apply_styles()

        # Сигналы
        self.update_plots_signal.connect(self.update_plots)
        self.log_signal.connect(self.log_message)

        # Таймер обновления графиков (10 fps)
        self.timer = QTimer()
        self.timer.timeout.connect(self.request_plot_update)
        self.timer.start(100)

        # Запускаем генераторы и приём команд
        self.update_generators()
        self.start_receiver()

    # ----------------------------------------------------------
    # Стилизация кнопок и элементов
    # ----------------------------------------------------------
    def apply_styles(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QRadioButton {
                spacing: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #ddd;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QTextEdit {
                font-family: monospace;
                font-size: 10pt;
            }
        """)

    # ----------------------------------------------------------
    # Интерфейс
    # ----------------------------------------------------------
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # Панель управления
        ctrl_group = QGroupBox("Управление")
        ctrl_layout = QHBoxLayout()
        self.start_btn = QPushButton("Старт")
        self.stop_btn = QPushButton("Стоп")
        self.apply_btn = QPushButton("Применить настройки")
        self.start_btn.clicked.connect(self.start_emulation)
        self.stop_btn.clicked.connect(self.stop_emulation)
        self.apply_btn.clicked.connect(self.update_generators)
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        ctrl_layout.addWidget(self.apply_btn)

        # Выбор адреса
        addr_group = QGroupBox("Адрес назначения")
        addr_layout = QVBoxLayout()
        self.local_radio = QRadioButton("Локальный (127.0.0.1)")
        self.broadcast_radio = QRadioButton("Широковещательный (255.255.255.255)")
        self.local_radio.setChecked(True)
        addr_layout.addWidget(self.local_radio)
        addr_layout.addWidget(self.broadcast_radio)
        addr_group.setLayout(addr_layout)
        ctrl_layout.addWidget(addr_group)
        ctrl_group.setLayout(ctrl_layout)
        main_layout.addWidget(ctrl_group)

        # Сценарии
        sc_group = QGroupBox("Сценарии (меняют диапазоны)")
        sc_layout = QHBoxLayout()
        for name in self.SCENARIOS:
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.apply_scenario(n))
            sc_layout.addWidget(btn)
        sc_group.setLayout(sc_layout)
        main_layout.addWidget(sc_group)

        # Ползунки Min/Max
        sliders_group = QGroupBox("Настройка диапазонов (Min / Max)")
        sliders_layout = QGridLayout()
        self.sliders = {}
        row = 0
        for ch, label in [("pulse", "Пульс"), ("emg", "ЭМГ"), ("eeg", "ЭЭГ"), ("gsr", "GSR")]:
            sliders_layout.addWidget(QLabel(label), row, 0)
            # Min
            min_slider = QSlider(Qt.Horizontal)
            min_slider.setRange(0, 4095)
            min_slider.setValue(getattr(self, f"{ch}_min"))
            min_slider.valueChanged.connect(lambda v, c=ch: self.on_min_changed(c, v))
            sliders_layout.addWidget(min_slider, row, 1)
            min_lbl = QLabel(str(getattr(self, f"{ch}_min")))
            min_lbl.setFixedWidth(40)
            sliders_layout.addWidget(min_lbl, row, 2)
            # Max
            max_slider = QSlider(Qt.Horizontal)
            max_slider.setRange(0, 4095)
            max_slider.setValue(getattr(self, f"{ch}_max"))
            max_slider.valueChanged.connect(lambda v, c=ch: self.on_max_changed(c, v))
            sliders_layout.addWidget(max_slider, row, 3)
            max_lbl = QLabel(str(getattr(self, f"{ch}_max")))
            max_lbl.setFixedWidth(40)
            sliders_layout.addWidget(max_lbl, row, 4)

            self.sliders[f"{ch}_min_slider"] = min_slider
            self.sliders[f"{ch}_max_slider"] = max_slider
            self.sliders[f"{ch}_min_label"] = min_lbl
            self.sliders[f"{ch}_max_label"] = max_lbl
            row += 1
        sliders_group.setLayout(sliders_layout)
        main_layout.addWidget(sliders_group)

        # Медицинские показатели (4 показателя)
        metrics_group = QGroupBox("Медицинские показатели")
        metrics_layout = QHBoxLayout()
        self.bpm_label = QLabel("BPM: --")
        self.bpm_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.stress_label = QLabel("Стресс: --%")
        self.stress_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.muscle_label = QLabel("Мышцы: --%")
        self.muscle_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.brain_label = QLabel("Мозг: --%")
        self.brain_label.setStyleSheet("font-size: 16pt; font-weight: bold;")

        metrics_layout.addWidget(self.bpm_label)
        metrics_layout.addWidget(self.stress_label)
        metrics_layout.addWidget(self.muscle_label)
        metrics_layout.addWidget(self.brain_label)
        metrics_group.setLayout(metrics_layout)
        main_layout.addWidget(metrics_group)

        # Графики (4 канала)
        plots_group = QGroupBox("Графики сигналов (реальное время)")
        plots_layout = QVBoxLayout()
        self.plot_widgets = {}
        self.plot_curves = {}
        for ch, title in [("pulse", "Пульс"), ("emg", "ЭМГ"), ("eeg", "ЭЭГ"), ("gsr", "GSR")]:
            pw = pg.PlotWidget()
            pw.setLabel('left', title)
            pw.setLabel('bottom', 'Последние 200 точек')
            pw.showGrid(x=True, y=True)
            curve = pw.plot(pen=pg.mkPen(color='c', width=2))
            self.plot_widgets[ch] = pw
            self.plot_curves[ch] = curve
            plots_layout.addWidget(pw)
        plots_group.setLayout(plots_layout)
        main_layout.addWidget(plots_group, stretch=2)

        # Лог команд
        log_group = QGroupBox("Лог команд от сервера (порт 5006)")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group, stretch=1)

    # Обработчики ползунков
    def on_min_changed(self, channel, value):
        if channel == "pulse":
            if value >= self.pulse_max:
                self.pulse_max = value + 1
                self.sliders["pulse_max_slider"].setValue(self.pulse_max)
            self.pulse_min = value
            self.sliders["pulse_min_label"].setText(str(value))
        elif channel == "emg":
            if value >= self.emg_max:
                self.emg_max = value + 1
                self.sliders["emg_max_slider"].setValue(self.emg_max)
            self.emg_min = value
            self.sliders["emg_min_label"].setText(str(value))
        elif channel == "eeg":
            if value >= self.eeg_max:
                self.eeg_max = value + 1
                self.sliders["eeg_max_slider"].setValue(self.eeg_max)
            self.eeg_min = value
            self.sliders["eeg_min_label"].setText(str(value))
        elif channel == "gsr":
            if value >= self.gsr_max:
                self.gsr_max = value + 1
                self.sliders["gsr_max_slider"].setValue(self.gsr_max)
            self.gsr_min = value
            self.sliders["gsr_min_label"].setText(str(value))

    def on_max_changed(self, channel, value):
        if channel == "pulse":
            if value <= self.pulse_min:
                self.pulse_min = value - 1
                self.sliders["pulse_min_slider"].setValue(self.pulse_min)
            self.pulse_max = value
            self.sliders["pulse_max_label"].setText(str(value))
        elif channel == "emg":
            if value <= self.emg_min:
                self.emg_min = value - 1
                self.sliders["emg_min_slider"].setValue(self.emg_min)
            self.emg_max = value
            self.sliders["emg_max_label"].setText(str(value))
        elif channel == "eeg":
            if value <= self.eeg_min:
                self.eeg_min = value - 1
                self.sliders["eeg_min_slider"].setValue(self.eeg_min)
            self.eeg_max = value
            self.sliders["eeg_max_label"].setText(str(value))
        elif channel == "gsr":
            if value <= self.gsr_min:
                self.gsr_min = value - 1
                self.sliders["gsr_min_slider"].setValue(self.gsr_min)
            self.gsr_max = value
            self.sliders["gsr_max_label"].setText(str(value))

    def apply_scenario(self, name):
        data = self.SCENARIOS[name]
        if len(data) == 9:  # новый формат с mental_base
            p_min, p_max, e_min, e_max, ee_min, ee_max, g_min, g_max, ml_base = data
        else:
            # на всякий случай, если старый сценарий
            p_min, p_max, e_min, e_max, ee_min, ee_max, g_min, g_max = data
            ml_base = 50
        self.pulse_min, self.pulse_max = p_min, p_max
        self.emg_min,   self.emg_max   = e_min, e_max
        self.eeg_min,   self.eeg_max   = ee_min, ee_max
        self.gsr_min,   self.gsr_max   = g_min, g_max
        # Обновляем ползунки
        self.sliders["pulse_min_slider"].setValue(p_min)
        self.sliders["pulse_max_slider"].setValue(p_max)
        self.sliders["emg_min_slider"].setValue(e_min)
        self.sliders["emg_max_slider"].setValue(e_max)
        self.sliders["eeg_min_slider"].setValue(ee_min)
        self.sliders["eeg_max_slider"].setValue(ee_max)
        self.sliders["gsr_min_slider"].setValue(g_min)
        self.sliders["gsr_max_slider"].setValue(g_max)
        # Базовая загруженность мозга будет использоваться при расчёте mental_load
        # сохраним в переменную
        self.default_mental_base = ml_base
        self.update_generators()

    def update_generators(self):
        limits = {
            "pulse": (self.pulse_min, self.pulse_max),
            "emg":   (self.emg_min, self.emg_max),
            "eeg":   (self.eeg_min, self.eeg_max),
            "gsr":   (self.gsr_min, self.gsr_max)
        }
        if not self.generators:
            self.generators = {
                "pulse": PulseGenerator(*limits["pulse"]),
                "emg":   EMGGenerator(*limits["emg"]),
                "eeg":   EEGGenerator(*limits["eeg"]),
                "gsr":   GSRGenerator(*limits["gsr"])
            }
        else:
            for name, (minv, maxv) in limits.items():
                self.generators[name].set_limits(minv, maxv)

    # ----------------------------------------------------------
    # Логика отправки данных и расчёт показателей
    # ----------------------------------------------------------
    def get_dest_address(self):
        return "127.0.0.1" if self.local_radio.isChecked() else "255.255.255.255"

    def build_packet(self, pulse, emg, eeg, gsr):
        pkt = bytearray(11)
        pkt[0] = 0xAA
        pkt[1] = (pulse >> 8) & 0xFF
        pkt[2] = pulse & 0xFF
        pkt[3] = (emg >> 8) & 0xFF
        pkt[4] = emg & 0xFF
        pkt[5] = (eeg >> 8) & 0xFF
        pkt[6] = eeg & 0xFF
        pkt[7] = (gsr >> 8) & 0xFF
        pkt[8] = gsr & 0xFF
        crc = 0
        for i in range(1, 9):
            crc ^= pkt[i]
        pkt[9] = crc
        pkt[10] = 0x55
        return pkt

    def calculate_local_metrics(self, pulse, emg, eeg, gsr):
        # BPM
        if pulse > 2800:
            now_ms = time.time() * 1000
            interval = now_ms - self.last_peak_time
            if 400 < interval < 1500:
                self.bpm = 60000.0 / interval
            self.last_peak_time = now_ms
        # Stress
        self.stress = int((gsr - 500) / 33)
        self.stress = max(0, min(100, self.stress))
        # Muscle
        self.emg_buffer.append(emg)
        if len(self.emg_buffer) == 50:
            amplitude = max(self.emg_buffer) - min(self.emg_buffer)
            self.muscle = int((amplitude - 100) / 24)
            self.muscle = max(0, min(100, self.muscle))
        # Mental Load: используем размах EEG + базовый уровень из сценария
        self.eeg_buffer.append(eeg)
        if len(self.eeg_buffer) == 50:
            eeg_amp = max(self.eeg_buffer) - min(self.eeg_buffer)
            # Нормализация: 0-4095 -> 0-100, плюс база (default_mental_base)
            raw_load = int(eeg_amp * 100 / 4095)
            # база по умолчанию 50, если не задана
            base = getattr(self, 'default_mental_base', 50)
            self.mental_load = max(0, min(100, (raw_load + base) // 2))

    def send_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.broadcast_radio.isChecked():
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        next_time = time.time()
        interval = 0.02   # 50 Hz

        while self.running:
            vals = {name: gen.update() for name, gen in self.generators.items()}
            self.current_values = vals
            self.calculate_local_metrics(vals["pulse"], vals["emg"], vals["eeg"], vals["gsr"])
            for ch in self.histories:
                self.histories[ch].append(vals[ch])
            pkt = self.build_packet(vals["pulse"], vals["emg"], vals["eeg"], vals["gsr"])
            try:
                sock.sendto(pkt, (self.get_dest_address(), 5005))
            except Exception as e:
                self.log_signal.emit(f"Ошибка отправки: {e}")
                break

            next_time += interval
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                time.sleep(sleep_time)
            else:
                next_time = time.time()
        sock.close()

    # ----------------------------------------------------------
    # Приём команд от сервера (порт 5006)
    # ----------------------------------------------------------
    def command_receiver(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', 5006))
        sock.settimeout(1.0)
        while not self.stop_receiver:
            try:
                data, addr = sock.recvfrom(1024)
                msg = data.decode().strip()
                self.log_signal.emit(f"Получено от {addr}: {msg}")
                if msg.startswith("STATS:"):
                    parts = msg[6:].split(',')
                    if len(parts) >= 3:
                        try:
                            self.bpm = float(parts[0])
                            self.stress = int(parts[1])
                            self.muscle = int(parts[2])
                            # если сервер присылает и mental load (4й параметр) – обновим
                            if len(parts) >= 4:
                                self.mental_load = int(parts[3])
                        except:
                            pass
            except socket.timeout:
                continue
            except Exception as e:
                self.log_signal.emit(f"Ошибка приёма: {e}")
                break
        sock.close()

    def start_receiver(self):
        self.stop_receiver = False
        self.recv_thread = threading.Thread(target=self.command_receiver, daemon=True)
        self.recv_thread.start()

    # ----------------------------------------------------------
    # Запуск / остановка
    # ----------------------------------------------------------
    def start_emulation(self):
        if self.running:
            return
        self.update_generators()
        self.running = True
        self.send_thread = threading.Thread(target=self.send_loop, daemon=True)
        self.send_thread.start()
        self.log_signal.emit("=== Эмуляция запущена ===")

    def stop_emulation(self):
        if not self.running:
            return
        self.running = False
        if self.send_thread:
            self.send_thread.join(timeout=1.0)
        self.log_signal.emit("=== Эмуляция остановлена ===")

    # ----------------------------------------------------------
    # Обновление UI (графики + цветовая индикация)
    # ----------------------------------------------------------
    def request_plot_update(self):
        if self.running:
            self.update_plots_signal.emit()

    def update_plots(self):
        for ch, curve in self.plot_curves.items():
            data = list(self.histories[ch])
            if data:
                curve.setData(data)

        # Обновляем тексты и цвета в зависимости от критичности
        self.bpm_label.setText(f"BPM: {self.bpm:.1f}")
        self.stress_label.setText(f"Стресс: {self.stress}%")
        self.muscle_label.setText(f"Мышцы: {self.muscle}%")
        self.brain_label.setText(f"Мозг: {self.mental_load}%")

        # Критические пороги
        bpm_critical = (self.bpm > 100) or (self.bpm < 60 and self.bpm > 0)
        stress_critical = self.stress > 70
        muscle_critical = self.muscle > 70
        brain_critical = self.mental_load > 70

        self.bpm_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: " + ("red" if bpm_critical else "black"))
        self.stress_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: " + ("red" if stress_critical else "black"))
        self.muscle_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: " + ("red" if muscle_critical else "black"))
        self.brain_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: " + ("red" if brain_critical else "black"))

    def log_message(self, text):
        self.log_text.append(text)

    def closeEvent(self, event):
        self.stop_emulation()
        self.stop_receiver = True
        if self.recv_thread:
            self.recv_thread.join(timeout=1.0)
        event.accept()

# --------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ESPEmulatorApp()
    window.show()
    sys.exit(app.exec_())