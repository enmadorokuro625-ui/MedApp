import socket
import time
import random
import math
import threading

# ------------------- НАСТРОЙКИ (как у ESP / esp_server) -------------------
SERVER_IP = "127.0.0.1"
UDP_SEND_PORT = 5005
UDP_RECV_PORT = 5006
SEND_INTERVAL = 0.02  # 50 Гц

ADC_MAX = 4095


class ESP32Emulator:
    def __init__(self):
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_recv.bind(("", UDP_RECV_PORT))
        self.sock_recv.settimeout(0.1)

        self.running = True
        self.start_time = time.time()
        self.mode = "ALL"

        # Фаза сердечного цикла 0..1 (один удар)
        self._beat_phase = 0.0

    def _pulse_adc(self) -> int:
        """Фотоплетизмография: baseline + узкий систолический пик + малый второй бугорок."""
        t = time.time() - self.start_time

        # ЧСС плавно «гуляет» в разумных пределах (уд/мин)
        bpm = 66 + 22 * (0.5 + 0.5 * math.sin(t * 0.09)) + 4 * math.sin(t * 0.6)
        bpm = max(52, min(98, bpm))

        # Сдвиг фазы за один тик
        self._beat_phase += SEND_INTERVAL * (bpm / 60.0)
        self._beat_phase %= 1.0
        u = self._beat_phase

        # Покойный уровень линии (как на реальном PPG до всплеска)
        baseline = 0.38 * ADC_MAX + 0.06 * ADC_MAX * math.sin(2 * math.pi * t * 0.11)

        # Основной систолический пик (гауссиана по фазе удара)
        peak1 = 0.52 * ADC_MAX * math.exp(-((u - 0.065) / 0.032) ** 2)
        # Второй небольшой компонент (дискротический отклик / отражённая волна)
        peak2 = 0.09 * ADC_MAX * math.exp(-((u - 0.21) / 0.045) ** 2)

        noise = random.gauss(0, 14)
        v = baseline + peak1 + peak2 + noise
        return int(max(0, min(ADC_MAX, v)))

    def _emg_adc(self) -> int:
        t = time.time() - self.start_time
        burst = 0.5 + 0.5 * math.sin(t * 0.35)
        carrier = 0.25 * ADC_MAX * (0.5 + 0.5 * math.sin(t * 37.0))
        v = 0.12 * ADC_MAX + burst * carrier + random.uniform(-80, 80)
        return int(max(0, min(ADC_MAX, v)))

    def _eeg_adc(self) -> int:
        t = time.time() - self.start_time
        v = (
            0.35 * ADC_MAX
            + 0.12 * ADC_MAX * math.sin(2 * math.pi * t * 6.0)
            + 0.08 * ADC_MAX * math.sin(2 * math.pi * t * 11.0)
            + random.uniform(-60, 60)
        )
        return int(max(0, min(ADC_MAX, v)))

    def _gsr_adc(self) -> int:
        t = time.time() - self.start_time
        v = 0.28 * ADC_MAX + 0.35 * ADC_MAX * (0.5 + 0.5 * math.sin(t * 0.08))
        v += random.uniform(-12, 12)
        return int(max(0, min(ADC_MAX, v)))

    def generate_raw_data(self):
        pulse = self._pulse_adc()
        emg = self._emg_adc()
        eeg = self._eeg_adc()
        gsr = self._gsr_adc()
        return pulse, emg, eeg, gsr

    def create_packet(self, pulse, emg, eeg, gsr):
        packet = bytearray(11)
        packet[0] = 0xAA
        packet[1] = (pulse >> 8) & 0xFF
        packet[2] = pulse & 0xFF
        packet[3] = (emg >> 8) & 0xFF
        packet[4] = emg & 0xFF
        packet[5] = (eeg >> 8) & 0xFF
        packet[6] = eeg & 0xFF
        packet[7] = (gsr >> 8) & 0xFF
        packet[8] = gsr & 0xFF
        crc = 0
        for i in range(1, 9):
            crc ^= packet[i]
        packet[9] = crc
        packet[10] = 0x55
        return packet

    def receiver_thread(self):
        print(f"[*] Emulator listening for commands on port {UDP_RECV_PORT}")
        while self.running:
            try:
                data, _ = self.sock_recv.recvfrom(1024)
                message = data.decode(errors="ignore")
                print(f"\n[EMU RECV] Message from server: {message}")
                if message.startswith("MODE:"):
                    self.mode = message.split(":")[1]
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error in receiver: {e}")

    def run(self):
        threading.Thread(target=self.receiver_thread, daemon=True).start()
        print(f"[*] Emulator sending to {SERVER_IP}:{UDP_SEND_PORT} at {1 / SEND_INTERVAL:.0f} Hz")
        print("[*] Pulse channel: PPG-like waveform, BPM ~52–98. Ctrl+C to stop.")

        try:
            while True:
                p, m, e, g = self.generate_raw_data()
                packet = self.create_packet(p, m, e, g)
                self.sock_send.sendto(packet, (SERVER_IP, UDP_SEND_PORT))
                time.sleep(SEND_INTERVAL)
        except KeyboardInterrupt:
            self.running = False
            print("\n[*] Emulator stopped")


if __name__ == "__main__":
    emu = ESP32Emulator()
    emu.run()
