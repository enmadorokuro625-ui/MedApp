import socket
import time
import threading
from collections import deque

# ------------------- НАСТРОЙКИ -------------------
ESP_IP = "192.168.0.127"        # IP-адрес ESP32 (измените под свой)
UDP_SEND_PORT = 5005            # Порт, куда ESP отправляет сырые данные
UDP_RECV_PORT = 5006            # Порт, на котором ESP слушает команды/статистику
BUFFER_SIZE = 11                # Длина пакета от ESP

# Параметры для расчёта BPM
PEAK_THRESHOLD = 2800
MIN_INTERVAL_MS = 400
MAX_INTERVAL_MS = 1500

# Для расчёта EMG
EMG_WINDOW = 50
emg_buffer = deque(maxlen=EMG_WINDOW)

# Глобальные переменные состояния
last_peak_time = 0
bpm = 0.0
stress = 50
muscle = 0

# ------------------- ФУНКЦИИ ОБРАБОТКИ -------------------
def calculate_bpm(raw_pulse):
    global last_peak_time, bpm
    if raw_pulse > PEAK_THRESHOLD:
        now_ms = time.time() * 1000
        interval = now_ms - last_peak_time
        if MIN_INTERVAL_MS < interval < MAX_INTERVAL_MS:
            bpm = 60000.0 / interval
            last_peak_time = now_ms
            return bpm
        if last_peak_time == 0:
            last_peak_time = now_ms
    return 0

def calculate_stress(raw_gsr):
    stress_val = int((raw_gsr - 500) / 33)
    return max(0, min(100, stress_val))

def calculate_muscle(raw_emg):
    global muscle
    emg_buffer.append(raw_emg)
    if len(emg_buffer) == EMG_WINDOW:
        emin = min(emg_buffer)
        emax = max(emg_buffer)
        amplitude = emax - emin
        muscle_val = int((amplitude - 100) / 24)
        muscle = max(0, min(100, muscle_val))
    return muscle

def decode_esp_packet(data):
    if len(data) != 11 or data[0] != 0xAA or data[10] != 0x55:
        return None
    crc = 0
    for i in range(1, 9):
        crc ^= data[i]
    if crc != data[9]:
        return None
    pulse = (data[1] << 8) | data[2]
    emg   = (data[3] << 8) | data[4]
    eeg   = (data[5] << 8) | data[6]
    gsr   = (data[7] << 8) | data[8]
    return (pulse, emg, eeg, gsr)

# ------------------- ОТПРАВКА НА ESP -------------------
def send_stats_to_esp(bpm, stress, muscle):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    message = f"STATS:{bpm:.1f},{stress},{muscle}"
    sock.sendto(message.encode(), (ESP_IP, UDP_RECV_PORT))
    sock.close()
    print(f"[SENT] {message}")

def send_mode_command(mode):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    message = f"MODE:{mode}"
    sock.sendto(message.encode(), (ESP_IP, UDP_RECV_PORT))
    sock.close()
    print(f"[CMD] {message}")

# ------------------- ПРИЁМ И ОСНОВНОЙ ЦИКЛ -------------------
def udp_listener():
    global bpm, stress, muscle
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', UDP_SEND_PORT))
    sock.settimeout(0.5)
    print(f"Listening for ESP data on port {UDP_SEND_PORT}...")

    last_send_time = 0
    send_interval = 1.0

    try:
        while True:
            try:
                data, addr = sock.recvfrom(BUFFER_SIZE)
                decoded = decode_esp_packet(data)
                if not decoded:
                    continue

                pulse, emg, eeg, gsr = decoded
                new_bpm = calculate_bpm(pulse)
                if new_bpm > 0:
                    bpm = new_bpm
                stress = calculate_stress(gsr)
                muscle = calculate_muscle(emg)

                # Теперь выводим и EEG
                print(f"P:{pulse:4d} EMG:{emg:4d} EEG:{eeg:4d} GSR:{gsr:4d} | BPM:{bpm:5.1f} Stress:{stress:3d}% Muscle:{muscle:3d}%")

                now = time.time()
                if now - last_send_time >= send_interval:
                    send_stats_to_esp(bpm, stress, muscle)
                    last_send_time = now

            except socket.timeout:
                pass
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        sock.close()


def console_handler():
    while True:
        cmd = input("\nEnter command (ALL, PLS, EMG, EEG, GSR, STATS, quit): ").strip().upper()
        if cmd == "QUIT":
            break
        if cmd in ["ALL", "PLS", "EMG", "EEG", "GSR", "STATS"]:
            send_mode_command(cmd)
        else:
            print("Unknown command. Available: ALL, PLS, EMG, EEG, GSR, STATS")

if __name__ == "__main__":
    listener_thread = threading.Thread(target=udp_listener, daemon=True)
    listener_thread.start()
    console_handler()
