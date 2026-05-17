import socket
import time
import threading
from collections import deque

# ------------------- НАСТРОЙКИ -------------------
ESP_IP = "192.168.0.100"        # IP-адрес ESP32 (измените под свой)
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
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>

// ── Настройки сети ────────────────────────────────────────────────
const char *WIFI_SSID = "TP-Link_7C13";
const char *WIFI_PASS = "1234567890";
const char *UDP_HOST = "255.255.255.255";
const uint16_t UDP_PORT = 5005;

// ── Пины (ESP32-S3 ADC1) ──────────────────────────────────────────
#define PIN_BUTTON 0   // Кнопка BOOT
#define PIN_PULSE  1 
#define PIN_EMG    2   
#define PIN_EEG    3   
#define PIN_GSR    4   
#define OLED_SDA   8
#define OLED_SCL   9

// ── Константы и Объекты ───────────────────────────────────────────
Adafruit_SSD1306 display(128, 64, &Wire, -1);
WiFiUDP udp;

#define GRAPH_WIDTH 75
uint16_t history[4][GRAPH_WIDTH]; 
int hist_idx = 0;

enum DisplayMode { ALL, FOCUS_PLS, FOCUS_EMG, FOCUS_EEG, FOCUS_GSR, MED_STATS, MODE_COUNT };
DisplayMode currentMode = ALL;

// Волатильные данные для ISR
volatile uint16_t v_raw[4];
volatile bool dataReady = false;
hw_timer_t *sampleTimer = nullptr;

// Медицинские показатели
float bpm = 0;
int stressLevel = 0;
int muscleLoad = 0;
uint32_t lastPeakTime = 0;

// ── Прерывание таймера (50Hz) ─────────────────────────────────────
void IRAM_ATTR onTimer() {
  v_raw[0] = analogRead(PIN_PULSE);
  v_raw[1] = analogRead(PIN_EMG);
  v_raw[2] = analogRead(PIN_EEG);
  v_raw[3] = analogRead(PIN_GSR);
  dataReady = true;
}

// ── Математика: BPM, Stress, Muscle ───────────────────────────────
void calculateMedical() {
  // 1. BPM: Детектор пика (порог 2800 для 12-бит)
  static uint16_t lastP = 0;
  if (v_raw[0] > 2800 && lastP <= 2800) { 
    uint32_t now = millis();
    uint32_t interval = now - lastPeakTime;
    if (interval > 400 && interval < 1500) { // 40-150 BPM
      bpm = 60000.0 / interval;
    }
    lastPeakTime = now;
  }
  lastP = v_raw[0];

  // 2. Stress (GSR): Чем выше влажность/проводимость, тем выше стресс
  stressLevel = map(v_raw[3], 500, 3800, 0, 100);
  stressLevel = constrain(stressLevel, 0, 100);

  // 3. Muscle (EMG): Размах сигнала (амплитуда)
  static uint16_t eMin = 4095, eMax = 0, count = 0;
  
  uint16_t currentEmg = v_raw[1]; 
  
  if (currentEmg < eMin) eMin = currentEmg;
  if (currentEmg > eMax) eMax = currentEmg;

  if (++count > 50) { 
    muscleLoad = map(eMax - eMin, 100, 2500, 0, 100);
    muscleLoad = constrain(muscleLoad, 0, 100);
    eMin = 4095; eMax = 0; count = 0;
  }
}

// ── Сеть: Отправка UDP (11 байт) ──────────────────────────────────
void sendPacket() {
  uint8_t pkt[11];
  pkt[0] = 0xAA;
  for (int i = 0; i < 4; i++) {
    pkt[1 + i * 2] = v_raw[i] >> 8;
    pkt[2 + i * 2] = v_raw[i] & 0xFF;
  }
  uint8_t crc = 0;
  for (uint8_t i = 1; i <= 8; i++) crc ^= pkt[i];
  pkt[9] = crc;
  pkt[10] = 0x55;

  udp.beginPacket(UDP_HOST, UDP_PORT);
  udp.write(pkt, 11);
  udp.endPacket();
}

// ── Графика: Автоскейл график ─────────────────────────────────────
void drawAutoscaleGraph(int x, int y, int w, int h, uint16_t data[], const char* label, uint16_t val) {
  uint16_t minV = 4095, maxV = 0;
  for (int i = 0; i < GRAPH_WIDTH; i++) {
    if (data[i] < minV) minV = data[i];
    if (data[i] > maxV) maxV = data[i];
  }
  if (maxV - minV < 20) { maxV += 10; minV = (minV > 10) ? minV - 10 : 0; }

  display.setTextColor(SSD1306_WHITE);
  display.setCursor(x, y + (h/2) - 3);
  display.print(label);

  for (int i = 0; i < GRAPH_WIDTH - 1; i++) {
    int i1 = (hist_idx + i) % GRAPH_WIDTH;
    int i2 = (hist_idx + i + 1) % GRAPH_WIDTH;
    int y1 = y + h - map(data[i1], minV, maxV, 0, h);
    int y2 = y + h - map(data[i2], minV, maxV, 0, h);
    display.drawLine(x + 18 + i, y1, x + 18 + i + 1, y2, SSD1306_WHITE);
  }
  display.setCursor(x + 98, y + (h/2) - 3);
  display.printf("%4u", val);
}


// ── Графика: Экран статистики ─────────────────────────────────────
void drawMedStats() {
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 18);
  display.print("HEART RATE:");
  display.setTextSize(2);
  display.setCursor(70, 16);
  display.printf("%.0f", bpm);
  display.setTextSize(1);
  display.setCursor(0, 36);
  display.printf("STRESS: %d%%", stressLevel);
  display.drawRect(70, 36, 50, 8, WHITE);
  display.fillRect(72, 38, map(stressLevel, 0, 100, 0, 46), 4, WHITE);
  display.setCursor(0, 48);
  display.printf("MUSCLE LOAD: %d%%", muscleLoad);
  display.setCursor(0, 57);
  display.print((stressLevel > 60) ? "STATE: ANXIOUS" : "STATE: CALM");
}

// ── Главный цикл отрисовки ────────────────────────────────────────
void updateUI() {
  display.clearDisplay();
  
  // Хедер (Желтая зона)
  display.fillRect(0, 0, 128, 14, SSD1306_WHITE);
  display.setTextColor(SSD1306_BLACK);
  display.setCursor(4, 3);
  display.print(WiFi.status() == WL_CONNECTED ? "UDP LIVE" : "OFFLINE");
  display.setCursor(70, 3);
  const char* mNames[] = {"DASH", "F:PLS", "F:EMG", "F:EEG", "F:GSR", "STATS"};
  display.print(mNames[currentMode]);

  // Обновляем историю
  hist_idx = (hist_idx + 1) % GRAPH_WIDTH;
  for(int i=0; i<4; i++) history[i][hist_idx] = v_raw[i];

  if (currentMode == ALL) {
    const char* labs[] = {"P", "M", "E", "G"};
    for (int i = 0; i < 4; i++) 
      drawAutoscaleGraph(0, 16 + (i * 12), 128, 10, history[i], labs[i], v_raw[i]);
  } 
  else if (currentMode == MED_STATS) {
    drawMedStats();
  }
  else {
    int sIdx = (int)currentMode - 1;
    const char* fLabs[] = {"PULSE", "EMG", "EEG", "GSR"};
    display.setTextSize(2);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(45, 18);
    display.printf("%4u", v_raw[sIdx]);
    display.setTextSize(1);
    drawAutoscaleGraph(0, 36, 128, 26, history[sIdx], fLabs[sIdx], v_raw[sIdx]);
  }
  display.display();
}

// ── Setup ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUTTON, INPUT_PULLUP);
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  Wire.begin(OLED_SDA, OLED_SCL);
  if (display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    display.clearDisplay();
    display.setTextColor(WHITE);
    display.println("BOOTING DrHouse...");
    display.display();
  }

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  // Таймер (API 2.x) - 1 тик = 1 мкс, 20000 тиков = 20мс (50Гц)
  sampleTimer = timerBegin(0, 80, true);
  timerAttachInterrupt(sampleTimer, &onTimer, true);
  timerAlarmWrite(sampleTimer, 20000, true);
  timerAlarmEnable(sampleTimer);

  udp.begin(UDP_PORT);
}

// ── Loop ──────────────────────────────────────────────────────────
void loop() {
  // Кнопка переключения режимов
  static bool lastBtn = HIGH;
  bool btn = digitalRead(PIN_BUTTON);
  if (btn == LOW && lastBtn == HIGH) {
    currentMode = (DisplayMode)((currentMode + 1) % MODE_COUNT);
    delay(50);
  }
  lastBtn = btn;

  if (dataReady) {
    dataReady = false;
    calculateMedical();
    
    if (WiFi.status() == WL_CONNECTED) {
      sendPacket();
    }

    // Отрисовка 10 раз в сек
    static uint32_t lastDisp = 0;
    if (millis() - lastDisp > 100) {
      lastDisp = millis();
      updateUI();
    }
  }
}
