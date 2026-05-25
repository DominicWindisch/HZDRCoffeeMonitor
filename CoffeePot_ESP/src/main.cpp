#include <Arduino.h>
#include <NimBLEDevice.h>
#include <HX711.h>

// --- PIN-BELEGUNG ---
#define TC1047_PWR D1
#define TC1047_Analog A0
#define HX711_GND D10
#define HX711_DATA D9
#define HX711_CLK D8
#define HX711_PWR D7
#define IO_Voltage A2

// --- ZEITEN ---
#define SLEEP_TIME_BATTERY_US 15000000ULL // 15 Sekunden Deep Sleep

HX711 scale;

// Generiert den Gerätenamen anhand der MAC-Adresse
String getDeviceName() {
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_BT);
  char name[32];
  snprintf(name, sizeof(name), "CoffeePot_%02X%02X", mac[4], mac[5]);
  return String(name);
}

// Baut das BTHome Paket und funkt es
void sendBTHomePacket(float temp, float volt, uint8_t battery, uint64_t mass, bool isCharging) {
  NimBLEDevice::init("");
  NimBLEAdvertising *pAdvertising = NimBLEDevice::getAdvertising();

  NimBLEAdvertisementData advData;
  NimBLEAdvertisementData scanRespData;

  scanRespData.setName(getDeviceName().c_str());
  advData.setFlags(BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP);

  std::string payload = "";
  payload += (char)0x40; 
  payload += (char)0x01;
  payload += (char)battery;

  int16_t t_val = (int16_t)(temp * 100);
  payload += (char)0x02;
  payload += (char)(t_val & 0xFF);
  payload += (char)((t_val >> 8) & 0xFF);

  uint16_t v_val = (uint16_t)(volt * 1000);
  payload += (char)0x0C;
  payload += (char)(v_val & 0xFF);
  payload += (char)((v_val >> 8) & 0xFF);

  uint32_t mass32 = (uint32_t)mass;
  payload += (char)0x3E;
  payload += (char)(mass32 & 0xFF);
  payload += (char)((mass32 >> 8) & 0xFF);
  payload += (char)((mass32 >> 16) & 0xFF);
  payload += (char)((mass32 >> 24) & 0xFF);

  NimBLEUUID bthomeUUID((uint16_t)0xFCD2);
  advData.setServiceData(bthomeUUID, payload);

  pAdvertising->setAdvertisementData(advData);
  pAdvertising->setScanResponseData(scanRespData);

  pAdvertising->start();
  delay(isCharging ? 800 : 1500); 
  pAdvertising->stop();
  
  NimBLEDevice::deinit(true); 
}

// Führt exakt EINEN kompletten Mess-Zyklus durch
bool performMeasurementAndSend() {
  // 1. SENSOREN BESTROMEN
  digitalWrite(TC1047_PWR, HIGH);
  digitalWrite(HX711_GND, LOW);
  digitalWrite(HX711_PWR, HIGH);

  // 2. WAAGE LESEN
  scale.power_up();
  uint64_t mass = 0;
  uint32_t startWait = millis();
  while (millis() - startWait < 1000) {
    if (scale.is_ready()) {
      mass = scale.read_average(5);
      break;
    }
    delay(5);
  }
  scale.power_down(); 

  // 3. TEMPERATUR LESEN
  uint32_t raw_temp = 0;
  for (int i = 0; i < 5; i++) {
    raw_temp += analogReadMilliVolts(TC1047_Analog);
    delay(2);
  }
  float temp = ((raw_temp / 5) * 0.1) - 50.0;
  digitalWrite(TC1047_PWR, LOW); 

  // 4. BATTERIE LESEN
  pinMode(IO_Voltage, INPUT);
  uint32_t raw_volt = 0;
  for (int i = 0; i < 8; i++) {
    raw_volt += analogReadMilliVolts(IO_Voltage);
    delay(2);
  }
  uint32_t millivolts = (raw_volt / 8) * 2;
  float volt = millivolts / 1000.0;
  
  int percent = map(millivolts, 3300, 4000, 0, 100);
  percent = constrain(percent, 0, 100); 

  bool isCharging = (volt >= 4);

  // --- SERIELLE AUSGABE FÜR DEBUGGING ---
  Serial.println("\n--- NEUE MESSUNG ---");
  Serial.printf("Waage (Raw) : %llu\n", mass);
  Serial.printf("Temperatur  : %.2f °C\n", temp);
  Serial.printf("Batterie    : %.2f V (%d %%)\n", volt, percent);
  Serial.printf("Modus       : %s\n", isCharging ? "LÄDT -> Bleibe wach" : "AKKU -> Gehe schlafen");
  Serial.println("Sende BTHome...");

  // 5. FUNKEN
  sendBTHomePacket(temp, volt, percent, mass, isCharging);

  return isCharging; 
}

void setup() {
  // =========================================================================
  // NOTLAUF-PRÜFUNG (Direkt als allererste Aktion, BEVOR Serial oder BLE starten!)
  // =========================================================================
  pinMode(IO_Voltage, INPUT);
  
  // Kurze Beruhigungspause für den ADC-Konverter (5ms)
  delay(5); 
  
  uint32_t raw_volt = 0;
  for (int i = 0; i < 8; i++) {
    raw_volt += analogReadMilliVolts(IO_Voltage);
  }
  float volt = ((raw_volt / 8) * 2) / 1000.0;

  // Wenn die Spannung unter 3.3V fällt, gehen wir in den extremen Stromsparmodus.
  // Die 2.0V-Untergrenze verhindert Fehlmessungen, falls gar keine Batterie dran hängt.
  if (volt < 3.3 && volt > 2.0) {
    // Wir funken nicht, wir schreiben nichts auf Serial. 
    // Wir legen uns sofort wieder für 5 Minuten schlafen (300 Sekunden).
    uint64_t emergency_sleep_us = 300000000ULL; 
    esp_sleep_enable_timer_wakeup(emergency_sleep_us);
    esp_deep_sleep_start();
  }
  // =========================================================================
  Serial.begin(115200);

  uint32_t t = millis();
  while (!Serial && (millis() - t < 3000)) { 
    delay(10); 
  }

  Serial.println("\n--- BOOT ---");

  // GPIOs initialisieren
  pinMode(TC1047_PWR, OUTPUT);
  pinMode(HX711_GND, OUTPUT);
  pinMode(HX711_PWR, OUTPUT);
  scale.begin(HX711_DATA, HX711_CLK);

  // Erste Messung durchführen
  bool isCharging = performMeasurementAndSend();

  // Wenn wir NICHT laden (Kabel ist ab), gehen wir lautlos und sofort in den Deep Sleep
  if (!isCharging) {
    esp_sleep_enable_timer_wakeup(SLEEP_TIME_BATTERY_US);
    esp_deep_sleep_start();
  }
}

void loop() {
  // --- WIR SIND IM LADEBETRIEB ---
  // (Hier macht Serial-Output Sinn, weil das Kabel steckt)
  delay(1000); 

  bool isCharging = performMeasurementAndSend();

  // Wenn das USB-Kabel während des Betriebs abgezogen wurde: lautlos schlafen gehen!
  if (!isCharging) {
    esp_sleep_enable_timer_wakeup(SLEEP_TIME_BATTERY_US);
    esp_deep_sleep_start();
  }
}