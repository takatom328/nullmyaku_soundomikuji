/*
  M5Stack IMU -> Jetson UDP sender
  Sends JSON payload:
  {
    "timestamp": 12.345,
    "ax": 0.01,
    "ay": -0.03,
    "az": 0.99,
    "acc_norm": 1.00,
    "event": "start|stop|none"
  }
*/

#include <M5Core2.h>
#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiUdp.h>

/*
  Optional microSD config:
  path: /imu_config.txt
  example:
    WIFI_SSID=your-ssid
    WIFI_PASS=your-password
    JETSON_IP=192.168.1.120
    JETSON_PORT=9001
    SEND_INTERVAL_MS=20
*/

char wifiSsid[64] = "YOUR_WIFI_SSID";
char wifiPass[64] = "YOUR_WIFI_PASS";
char jetsonIp[32] = "192.168.1.100";
uint16_t jetsonPort = 9001;
uint32_t sendIntervalMs = 20;  // ~50Hz

WiFiUDP udp;
uint32_t lastSendMs = 0;
uint32_t lastUiMs = 0;
uint32_t lastReconnectMs = 0;
uint32_t packetCount = 0;
bool lastSendOk = false;
bool configLoadedFromSd = false;
String lastEvent = "none";
float lastAx = 0.0f;
float lastAy = 0.0f;
float lastAz = 1.0f;
float lastAccNorm = 0.0f;

enum UiState {
  UI_WAITING = 0,
  UI_MEASURING = 1,
  UI_DONE = 2,
};

UiState uiState = UI_WAITING;
uint32_t doneStateStartMs = 0;

String trimCopy(const String& src) {
  String s = src;
  s.trim();
  return s;
}

void updateConfigValue(const String& key, const String& value) {
  if (key == "WIFI_SSID") {
    value.toCharArray(wifiSsid, sizeof(wifiSsid));
  } else if (key == "WIFI_PASS") {
    value.toCharArray(wifiPass, sizeof(wifiPass));
  } else if (key == "JETSON_IP") {
    value.toCharArray(jetsonIp, sizeof(jetsonIp));
  } else if (key == "JETSON_PORT") {
    jetsonPort = (uint16_t) value.toInt();
  } else if (key == "SEND_INTERVAL_MS") {
    sendIntervalMs = (uint32_t) value.toInt();
    if (sendIntervalMs < 10) {
      sendIntervalMs = 10;
    }
  }
}

bool loadConfigFromSD() {
#ifdef TFCARD_CS_PIN
  if (!SD.begin(TFCARD_CS_PIN, SPI, 40000000)) {
    return false;
  }
#else
  if (!SD.begin()) {
    return false;
  }
#endif

  File file = SD.open("/imu_config.txt", FILE_READ);
  if (!file) {
    return false;
  }

  while (file.available()) {
    String line = file.readStringUntil('\n');
    line = trimCopy(line);
    if (line.length() == 0 || line.startsWith("#")) {
      continue;
    }

    int separator = line.indexOf('=');
    if (separator <= 0) {
      continue;
    }

    String key = trimCopy(line.substring(0, separator));
    String value = trimCopy(line.substring(separator + 1));
    if (value.length() == 0) {
      continue;
    }

    updateConfigValue(key, value);
  }
  file.close();
  return true;
}

void project3D(float x, float y, float z, int originX, int originY, float scale, int* sx, int* sy) {
  const float px = (x - y) * 0.7071f;
  const float py = ((x + y) * 0.35f - z) * 0.7071f;
  *sx = originX + (int)(px * scale);
  *sy = originY + (int)(py * scale);
}

void drawImuGraph() {
  const int panelX = 172;
  const int panelY = 8;
  const int panelW = 142;
  const int panelH = 224;
  const int originX = panelX + panelW / 2;
  const int originY = panelY + panelH / 2 + 26;
  const float axisScale = 42.0f;

  M5.Lcd.drawRect(panelX, panelY, panelW, panelH, DARKGREY);
  M5.Lcd.setTextSize(1);
  M5.Lcd.setTextColor(CYAN, BLACK);
  M5.Lcd.setCursor(panelX + 6, panelY + 6);
  M5.Lcd.println("IMU 3D View");

  int xAxisX = originX, xAxisY = originY;
  int yAxisX = originX, yAxisY = originY;
  int zAxisX = originX, zAxisY = originY;
  project3D(1.0f, 0.0f, 0.0f, originX, originY, axisScale, &xAxisX, &xAxisY);
  project3D(0.0f, 1.0f, 0.0f, originX, originY, axisScale, &yAxisX, &yAxisY);
  project3D(0.0f, 0.0f, 1.0f, originX, originY, axisScale, &zAxisX, &zAxisY);

  M5.Lcd.drawLine(originX, originY, xAxisX, xAxisY, RED);
  M5.Lcd.drawLine(originX, originY, yAxisX, yAxisY, GREEN);
  M5.Lcd.drawLine(originX, originY, zAxisX, zAxisY, BLUE);
  M5.Lcd.fillCircle(originX, originY, 2, WHITE);
  M5.Lcd.drawCircle(originX, originY, 44, DARKGREY);

  float nx = 0.0f;
  float ny = 0.0f;
  float nz = 0.0f;
  if (lastAccNorm > 0.0001f) {
    nx = lastAx / lastAccNorm;
    ny = lastAy / lastAccNorm;
    nz = lastAz / lastAccNorm;
  }

  int vecX = originX, vecY = originY;
  project3D(nx, ny, nz, originX, originY, axisScale, &vecX, &vecY);
  M5.Lcd.drawLine(originX, originY, vecX, vecY, YELLOW);
  M5.Lcd.fillCircle(vecX, vecY, 4, ORANGE);

  M5.Lcd.setTextColor(WHITE, BLACK);
  M5.Lcd.setCursor(panelX + 6, panelY + panelH - 58);
  M5.Lcd.printf("ax: %+0.3f", lastAx);
  M5.Lcd.setCursor(panelX + 6, panelY + panelH - 44);
  M5.Lcd.printf("ay: %+0.3f", lastAy);
  M5.Lcd.setCursor(panelX + 6, panelY + panelH - 30);
  M5.Lcd.printf("az: %+0.3f", lastAz);
  M5.Lcd.setCursor(panelX + 6, panelY + panelH - 16);
  M5.Lcd.printf("|a|:%0.3f", lastAccNorm);
}

const char* uiStateLabel() {
  if (uiState == UI_MEASURING) {
    return "MEASURING";
  }
  if (uiState == UI_DONE) {
    return "DONE";
  }
  return "WAITING";
}

uint16_t uiStateColor() {
  if (uiState == UI_MEASURING) {
    return RED;
  }
  if (uiState == UI_DONE) {
    return CYAN;
  }
  return WHITE;
}

void drawStatus() {
  const uint32_t now = millis();
  if (now - lastUiMs < 300) {
    return;
  }
  lastUiMs = now;

  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setTextColor(WHITE, BLACK);
  M5.Lcd.setTextSize(2);
  M5.Lcd.setCursor(8, 8);
  M5.Lcd.println("M5 IMU Sender");
  M5.Lcd.fillCircle(146, 22, 9, uiStateColor());
  M5.Lcd.drawCircle(146, 22, 9, DARKGREY);

  M5.Lcd.setTextSize(1);
  M5.Lcd.setCursor(8, 44);
  M5.Lcd.printf("State: %s\n", uiStateLabel());
  M5.Lcd.printf("WiFi: %s\n", WiFi.status() == WL_CONNECTED ? "CONNECTED" : "DISCONNECTED");
  M5.Lcd.printf("Local IP: %s\n", WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : "-");
  M5.Lcd.printf("Target : %s:%u\n", jetsonIp, jetsonPort);
  M5.Lcd.printf("Interval: %lu ms\n", (unsigned long)sendIntervalMs);
  M5.Lcd.printf("Packets : %lu\n", (unsigned long)packetCount);
  M5.Lcd.printf("LastEvt : %s\n", lastEvent.c_str());
  M5.Lcd.printf("AccNorm : %.3f\n", lastAccNorm);
  M5.Lcd.printf("LastUDP : %s\n", lastSendOk ? "OK" : "FAIL");
  M5.Lcd.printf("ConfigSD: %s\n", configLoadedFromSd ? "LOADED" : "DEFAULT");
  M5.Lcd.println("BtnA=start BtnB=stop");

  drawImuGraph();
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(wifiSsid, wifiPass);
  uint32_t startMs = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startMs < 15000) {
    drawStatus();
    delay(200);
  }
}

void sendImuPacket(const char* eventLabel) {
  float ax = 0.0f;
  float ay = 0.0f;
  float az = 0.0f;
  M5.IMU.getAccelData(&ax, &ay, &az);
  lastAx = ax;
  lastAy = ay;
  lastAz = az;

  float accNorm = sqrtf(ax * ax + ay * ay + az * az);
  lastAccNorm = accNorm;
  float timestampSec = millis() / 1000.0f;

  char payload[256];
  snprintf(
    payload,
    sizeof(payload),
    "{\"timestamp\":%.3f,\"ax\":%.5f,\"ay\":%.5f,\"az\":%.5f,\"acc_norm\":%.5f,\"event\":\"%s\"}",
    timestampSec,
    ax,
    ay,
    az,
    accNorm,
    eventLabel
  );

  udp.beginPacket(jetsonIp, jetsonPort);
  udp.write((const uint8_t*)payload, strlen(payload));
  lastSendOk = udp.endPacket() == 1;
  if (lastSendOk) {
    packetCount++;
  }
}

void setup() {
  M5.begin(true, true, true, true);
  M5.Lcd.setRotation(1);
  M5.Lcd.setTextFont(2);
  configLoadedFromSd = loadConfigFromSD();
  M5.IMU.Init();
  connectWiFi();
  drawStatus();
}

void loop() {
  M5.update();
  const uint32_t now = millis();

  if (uiState == UI_DONE && (now - doneStateStartMs) >= 5000) {
    uiState = UI_WAITING;
  }

  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastReconnectMs > 2000) {
      WiFi.disconnect();
      WiFi.begin(wifiSsid, wifiPass);
      lastReconnectMs = now;
    }
    drawStatus();
    delay(20);
    return;
  }

  if (now - lastSendMs >= sendIntervalMs) {
    const char* eventLabel = "none";
    if (M5.BtnA.wasPressed()) {
      eventLabel = "start";
      uiState = UI_MEASURING;
    } else if (M5.BtnB.wasPressed()) {
      eventLabel = "stop";
      uiState = UI_DONE;
      doneStateStartMs = now;
    }

    lastEvent = String(eventLabel);
    sendImuPacket(eventLabel);
    lastSendMs = now;
  }
  drawStatus();
}
