#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

// Neue "Flat-16" API Struktur für eine Kanne
struct PotData
{
    uint8_t fill;        // 3 Bit (0-6)
    uint8_t batt;        // 1 Bit (0=OK, 1=Low)
    uint8_t conn;        // 1 Bit (0=Verbunden, 1=Offline)
    uint8_t is_brewing;  // 1 Bit (0=Normal, 1=Kocht)
    uint8_t steam_level; // 2 Bit (0=Kalt, 1-3 Schwaden)
    uint8_t age_mins;    // 8 Bit (0-255 Minuten)

    uint16_t pack()
    {
        return (fill & 0x07) |
               ((batt & 0x01) << 3) |
               ((conn & 0x01) << 4) |
               ((is_brewing & 0x01) << 5) |
               ((steam_level & 0x03) << 6) |
               ((age_mins & 0xFF) << 8);
    }
};

BLEAdvertising *pAdvertising;

void setup()
{
    Serial.begin(115200);

    uint32_t t = millis();
    while (!Serial && (millis() - t < 3000))
    {
        delay(10);
    }

    Serial.println("\n--- BOOT ESP BROADCASTER ---");

    // BLE darf nur einmalig initialisiert werden!
    BLEDevice::init("CoffeeProxy");
    pAdvertising = BLEDevice::getAdvertising();

    Serial.println("Warte auf serielle Daten...");
    Serial.println("Erwartetes Format (30 Tokens): 08:30 22.05.2026 4  [fill batt conn is_brewing steam age_mins] ...");
}

void parseAndBroadcast(String input)
{
    // Puffer vergrößert für längeren String
    char buf[256]; 
    input.toCharArray(buf, sizeof(buf));

    const char *delimiters = " :.,;";
    char *token = strtok(buf, delimiters);
    
    // Array vergrößert, da wir jetzt 30 Tokens (6 Header + 4x6 Kannen) erwarten
    int tokens[35]; 
    int tokenCount = 0;

    while (token != NULL && tokenCount < 35)
    {
        tokens[tokenCount++] = atoi(token);
        token = strtok(NULL, delimiters);
    }

    if (tokenCount < 30)
    {
        Serial.printf("Fehler: Zu wenige Parameter! (Erhalten: %d, Erwartet: 30)\n", tokenCount);
        return;
    }

    // --- 17-Byte Payload zusammenbauen ---
    uint8_t payload[17];

    // Exklusiver Header (0xCAFE in Little Endian -> FE CA)
    payload[0] = 0xFE;
    payload[1] = 0xCA;

    // Zeit & Datum
    payload[2] = tokens[0]; // Stunden
    payload[3] = tokens[1]; // Minuten
    payload[4] = tokens[2]; // Tag
    payload[5] = tokens[3]; // Monat

    // Jahr als 16-Bit Integer (Bytes 6 und 7)
    uint16_t year = tokens[4];       
    payload[6] = year & 0xFF;        // Low Byte 
    payload[7] = (year >> 8) & 0xFF; // High Byte 

    payload[8] = tokens[5]; // N (Anzahl der Kannen)

    // Kannen-Daten packen (startet jetzt bei Byte 9)
    PotData pots[4];
    int offset = 6;

    for (int i = 0; i < 4; i++)
    {
        pots[i].fill        = tokens[offset++];
        pots[i].batt        = tokens[offset++];
        pots[i].conn        = tokens[offset++];
        pots[i].is_brewing  = tokens[offset++];
        pots[i].steam_level = tokens[offset++];
        pots[i].age_mins    = tokens[offset++];

        uint16_t val = pots[i].pack();
        payload[9 + i * 2]     = val & 0xFF;            // Low Byte
        payload[9 + i * 2 + 1] = (val >> 8) & 0xFF;     // High Byte
    }

    // --- BLE Paket senden ---
    BLEAdvertisementData oAdvertisementData = BLEAdvertisementData();
    std::string manufData((char *)payload, 17); // 17 Bytes Länge!

    oAdvertisementData.setManufacturerData(manufData);
    pAdvertising->setAdvertisementData(oAdvertisementData);

    Serial.printf("Sende BLE Paket: %02d:%02d %02d.%02d.%04d | Payload generiert.\n",
                  payload[2], payload[3], payload[4], payload[5], year);

    pAdvertising->start();
    delay(500);
    pAdvertising->stop();
    Serial.println("Broadcast beendet.");
}

void loop()
{
    // Serielle Schnittstelle abhören
    if (Serial.available() > 0)
    {
        String input = Serial.readStringUntil('\n');
        input.trim(); // Entfernt eventuelle \r am Ende

        if (input.length() > 20)
        { // Ignoriert versehentliche leere Zeilen/kurzen Müll
            parseAndBroadcast(input);
        }
    }
}