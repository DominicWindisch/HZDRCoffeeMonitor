#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEAdvertising.h>

// Struktur für eine Kanne (16 Bit)
struct PotData
{
    uint8_t fill;    // 3 Bit
    uint8_t battery; // 1 Bit
    uint8_t state;   // 2 Bit
    uint8_t conn;    // 1 Bit
    uint8_t temp;    // 7 Bit

    uint16_t pack()
    {
        return (fill & 0x07) |
               ((battery & 0x01) << 3) |
               ((state & 0x03) << 4) |
               ((conn & 0x01) << 6) |
               ((temp & 0x7F) << 7);
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
    Serial.println("Format z.B.: 08:30 22.05.2026 4  6 0 0 0 82  4 0 0 0 75  1 0 3 1 35  0 0 0 0 20");
}

void parseAndBroadcast(String input)
{
    char buf[128];
    input.toCharArray(buf, sizeof(buf));

    const char *delimiters = " :.,;";
    char *token = strtok(buf, delimiters);
    int tokens[30];
    int tokenCount = 0;

    while (token != NULL && tokenCount < 30)
    {
        tokens[tokenCount++] = atoi(token);
        token = strtok(NULL, delimiters);
    }

    if (tokenCount < 26)
    {
        Serial.printf("Fehler: Zu wenige Parameter! (Erhalten: %d)\n", tokenCount);
        return;
    }

    // --- 17-Byte Payload zusammenbauen ---
    uint8_t payload[17];

    // Header (0x3412)
    payload[0] = 0x34;
    payload[1] = 0x12;

    // Zeit & Datum
    payload[2] = tokens[0]; // Stunden
    payload[3] = tokens[1]; // Minuten
    payload[4] = tokens[2]; // Tag
    payload[5] = tokens[3]; // Monat

    // Jahr als 16-Bit Integer (Bytes 6 und 7)
    uint16_t year = tokens[4];       // 2026
    payload[6] = year & 0xFF;        // Low Byte (0xEA)
    payload[7] = (year >> 8) & 0xFF; // High Byte (0x07)

    payload[8] = tokens[5]; // N (Anzahl der Kannen)

    // Kannen-Daten packen (startet jetzt bei Byte 9)
    PotData pots[4];
    int offset = 6;

    for (int i = 0; i < 4; i++)
    {
        pots[i].fill = tokens[offset++];
        pots[i].battery = tokens[offset++];
        pots[i].state = tokens[offset++];
        pots[i].conn = tokens[offset++];
        pots[i].temp = tokens[offset++];

        uint16_t val = pots[i].pack();
        payload[9 + i * 2] = val & 0xFF;            // Low Byte
        payload[9 + i * 2 + 1] = (val >> 8) & 0xFF; // High Byte
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