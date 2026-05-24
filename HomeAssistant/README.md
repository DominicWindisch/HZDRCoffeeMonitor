In configuration.yaml, add:
```yaml
homeassistant:
  packages: !include_dir_named packages
```

Then, create a folder 'packages' right next to configuration.yaml and place hzdr_coffee_monitor.yaml in there.


### ⚠️ WICHTiger Hinweis zu Trend-Sensoren (Stand HA 2024.1+)
Home Assistant unterstützt die Konfiguration von Trend-Sensoren **nicht mehr via YAML**. Diese müssen zwingend über die Benutzeroberfläche (Helfer) angelegt werden. 

Aufgrund eines UX-Fehlers in Home Assistant sind die erweiterten Einstellungen (`min_gradient`, `sample_duration`) bei der Neuerstellung eines Helfers **unsichtbar**. Sie können erst nachträglich konfiguriert werden!

**Vorgehen zum Anlegen der Sensoren:**
1. Gehe in HA auf `Einstellungen` -> `Geräte & Dienste` -> `Helfer`.
2. Klicke auf `+ Helfer erstellen` und wähle **Trend-Sensor**.
3. **Schritt 1 (Basis-Setup):** Vergib nur den Namen und wähle die Entität aus. Klicke auf `Erstellen`.
4. **Schritt 2 (Erweiterte Optionen):** Suche den soeben erstellten Helfer in der Liste und klicke ihn an.
5. Klicke oben rechts auf das **Zahnrad-Symbol** und wähle **Optionen**.
6. Jetzt sind die versteckten Parameter sichtbar und können eingetragen werden.

**Benötigte Sensoren für dieses Projekt:**

**1. Kanne 1: Spannung fällt (Erkennt ob Kanne von der Basis genommen wird)**
* **Name:** `kanne1 voltage falling` *(Wichtig für korrekte ID!)*
* **Entität:** `sensor.coffeepot_5dd2_5dd2_spannung`
* **Ergebnis umkehren (Invert):** ✅ Aktiviert
* **Maximales Alter der Messwerte:** `1200`

**2. Kanne 1: Temperatur steigt (Verhindert Fehlerkennung beim Abkühlen)**
* **Name:** `kanne1 temp rising` *(Wichtig für korrekte ID!)*
* **Entität:** `sensor.coffeepot_5dd2_5dd2_temperatur`
* **Maximales Alter der Messwerte:** `1800`
* **Minimale Steigung (Min Gradient):** `0.0005`
* **Ergebnis umkehren (Invert):** ❌ Deaktiviert


Restart homeassistant (reloading YAML is not enough).

# Dashboard:
- add addon 'studio server'
- use that to upload the coffee_sprites to config/www/coffee/