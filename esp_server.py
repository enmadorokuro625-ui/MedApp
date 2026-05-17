import socket
import time
import math
import sys
import requests
from collections import deque

# Настройки
API_URL = "http://localhost:5000/api/update_data" # Куда шлем данные
UDP_SEND_PORT = 5005
BUFFER_SIZE = 11

# 12-бит АЦП ESP32: 0..4095 — все физические каналы в одной шкале
ADC_MAX = 4095

# Параметры BPM (пульс в уд/мин не выше ~150 при «максимуме» по шкале АЦП)
MIN_BPM, MAX_BPM = 40, 150
MIN_INTERVAL = 60000 / MAX_BPM
MAX_INTERVAL = 60000 / MIN_BPM

# Буферы для расчетов
pulse_raw = deque(maxlen=50)
pulse_filtered = deque(maxlen=40)
emg_buffer = deque(maxlen=50)
eeg_buffer = deque(maxlen=100)

# Переменные состояния
bpm, stress, muscle = 0, 50, 0
alpha_rhythm, beta_rhythm = 50, 30
eeg_level_smooth = 0.0
last_peak = 0

def _clamp_adc(v):
    return max(0, min(ADC_MAX, int(v)))

def hash_peak(filtered):
    global bpm, last_peak
    if len(filtered) < 3:
        return min(MAX_BPM, max(MIN_BPM, bpm)) if bpm else bpm
    v1, v2, v3 = list(filtered)[-3:]
    if v2 > v1 and v2 > v3:
        now = time.time() * 1000
        if last_peak:
            interval = now - last_peak
            if MIN_INTERVAL < interval < MAX_INTERVAL:
                bpm = 60000 / interval
        last_peak = now
    return min(MAX_BPM, max(MIN_BPM, bpm)) if bpm else bpm

def process_data(pulse, emg, eeg, gsr):
    global stress, muscle, alpha_rhythm, beta_rhythm, bpm, eeg_level_smooth
    pulse = _clamp_adc(pulse)
    emg = _clamp_adc(emg)
    eeg = _clamp_adc(eeg)
    gsr = _clamp_adc(gsr)

    pulse_raw.append(pulse)
    if len(pulse_raw) < 10:
        return bpm

    dc = sum(pulse_raw) / len(pulse_raw)
    pulse_filtered.append(pulse - dc)
    new_bpm = hash_peak(pulse_filtered)

    # GSR 0..4095 -> стресс 0..100 (ровная шкала относительно полного диапазона АЦП)
    stress = max(0, min(100, int(gsr * 100.0 / ADC_MAX)))

    emg_buffer.append(emg)
    if len(emg_buffer) == emg_buffer.maxlen:
        amp = max(emg_buffer) - min(emg_buffer)
        muscle = max(0, min(100, int(amp * 100.0 / ADC_MAX)))

    # ЭЭГ: работаем в нормированных единицах 0..1, на сайте «максимум АЦП» -> ~100
    eeg_n = eeg / float(ADC_MAX)
    eeg_buffer.append(eeg_n)
    activity = 0.0
    if len(eeg_buffer) > 10:
        mean = sum(eeg_buffer) / len(eeg_buffer)
        var = sum((x - mean) ** 2 for x in list(eeg_buffer)[-10:]) / 10.0
        activity = min(100.0, math.sqrt(max(0.0, var)) * 420.0)

    eeg_inst = min(100.0, eeg_n * 100.0)
    eeg_level_smooth = eeg_level_smooth * 0.88 + eeg_inst * 0.12

    alpha_target = max(0.0, min(100.0, eeg_level_smooth * 0.65 + activity * 0.35))
    beta_target = max(0.0, min(100.0, 15.0 + stress * 0.45 + muscle * 0.35 + activity * 0.35))
    alpha_rhythm = alpha_rhythm * 0.9 + alpha_target * 0.1
    beta_rhythm = beta_rhythm * 0.9 + beta_target * 0.1
    return new_bpm

def determine_state():
    b = min(MAX_BPM, max(0, bpm))
    if b > 110:
        return "Аритмия"
    if stress > 70:
        return "Стресс"
    if muscle > 80:
        return "Перегрузка"
    return "Норма"

def decode_packet(data):
    if len(data) != 11 or data[0] != 0xAA or data[10] != 0x55: return None
    crc = 0
    for i in range(1, 9): crc ^= data[i]
    if crc != data[9]: return None
    return ((data[1]<<8)|data[2], (data[3]<<8)|data[4], (data[5]<<8)|data[6], (data[7]<<8)|data[8])

def udp_listener(username):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', UDP_SEND_PORT))
    print(f"[RUNNING] ESP Server for {username}. No Logging.")

    last_send_time = 0

    while True:
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
            decoded = decode_packet(data)
            if not decoded: continue
            
            p, m, e, g = decoded
            new_bpm = process_data(p, m, e, g)
            state = determine_state()

            # Отправляем данные в API раз в 100мс (чтобы не спамить HTTP запросами)
            now = time.time()
            if now - last_send_time > 0.1:
                # Пока пиковый детектор не выдал ЧСС — оценка по уровню АЦП (0..4095 -> ~40..150)
                bpm_display = float(bpm) if bpm else max(
                    MIN_BPM, min(MAX_BPM, round(p * (MAX_BPM / float(ADC_MAX)), 1))
                )
                bpm_display = min(MAX_BPM, max(0.0, bpm_display))
                payload = {
                    "username": username,
                    "bpm": round(bpm_display, 1),
                    "stress": stress,
                    "muscle": muscle,
                    "alpha": round(min(100.0, max(0.0, eeg_level_smooth)), 1),
                    "beta": round(beta_rhythm, 1),
                    "state": state,
                }
                try:
                    requests.post(API_URL, json=payload, timeout=0.05)
                except:
                    pass # API пока не запущено или занято
                last_send_time = now

        except Exception as e:
            print(f"[UDP ERROR] {e}")

if __name__ == "__main__":
    user = sys.argv[1] if len(sys.argv) > 1 else "testuser"
    udp_listener(user)