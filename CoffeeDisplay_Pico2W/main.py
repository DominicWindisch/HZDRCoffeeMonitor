import bluetooth
import epd_v2
import machine
import struct
import time
import framebuf
from hzdr_logo import logo_data, logo_width, logo_height

from writer import Writer
import font_clock
import font_text

print("=== Coffee Monitor: Modern Tile Dashboard ===")

# --- BLE SCANNER SETUP ---
ble = bluetooth.BLE()
ble.active(True)

epd = epd_v2.EPD_7in5_B()

# --- HARDWARE BUTTON (Für Test-Refreshes) ---
btn0 = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_UP)
manual_refresh_requested = False

def btn_callback(pin):
    global manual_refresh_requested
    manual_refresh_requested = True
btn0.irq(trigger=machine.Pin.IRQ_FALLING, handler=btn_callback)

# --- BLUETOOTH IRQ ---
new_ble_data = None
ble_update_flag = False

def bt_irq(event, data):
    global new_ble_data, ble_update_flag
    if event == 5: # _IRQ_SCAN_RESULT
        _, _, _, _, adv_data = data
        
        i = 0
        found_data = None
        while i < len(adv_data):
            length = adv_data[i]
            type = adv_data[i+1]
            if type == 0xFF: # Manufacturer Specific Data
                found_data = adv_data[i+2 : i+1+length]
                break
            i += 1 + length
            
        # Wir brauchen die vollen 17 Bytes (2 Header + 15 Payload)
        if found_data and found_data[0:2] == b'\x34\x12' and len(found_data) >= 17:
            new_ble_data = bytes(found_data[2:17]) # Schneidet exakt die 15 Payload-Bytes aus
            ble_update_flag = True

# Scan starten: Dauerhaft, passiv, alle 30s Scan-Fenster
ble.gap_scan(0, 30000, 30000)
ble.irq(bt_irq)

# --- ZEICHEN-FUNKTIONEN ---
class DisplayProxy(framebuf.FrameBuffer):
    def __init__(self, fb_data, w, h, fmt):
        super().__init__(fb_data, w, h, fmt)
        self.width = w
        self.height = h
    
display_proxy = DisplayProxy(epd.imageblack, 800, 480, framebuf.MONO_HLSB)
clock_writer = Writer(display_proxy, font_clock)
text_writer = Writer(display_proxy, font_text)

logo_fb = framebuf.FrameBuffer(
    logo_data, 
    logo_width, 
    logo_height, 
    framebuf.MONO_HLSB
)

def dither_rect(x, y, w, h):
    for py in range(y, y + h):
        start_x = x if py % 2 == 0 else x + 1
        for px in range(start_x, x + w, 2):
            display_proxy.pixel(px, py, 0x00)

def draw_severin(x, y):
    display_proxy.fill_rect(x + 20, y, 70, 8, 0x00)
    display_proxy.fill_rect(x + 45, y - 6, 20, 6, 0x00)
    display_proxy.fill_rect(x + 10, y, 10, 12, 0x00)
    display_proxy.line(x + 10, y + 12, x + 20, y + 20, 0x00)
    display_proxy.fill_rect(x + 90, y, 40, 12, 0x00) 
    display_proxy.fill_rect(x + 118, y, 12, 140, 0x00) 
    display_proxy.fill_rect(x + 95, y + 130, 25, 10, 0x00) 
    for w in range(5):
        display_proxy.line(x + 20 - w, y + 8, x + 12 - w, y + 170, 0x00)
        display_proxy.line(x + 90 + w, y + 8, x + 98 + w, y + 170, 0x00)
    display_proxy.fill_rect(x + 7, y + 170, 96, 8, 0x00)

def draw_no_wifi(x, y):
    """Zeichnet ein massives, blockiges WLAN-Wedge (Balken) mit einem dicken X"""
    # WLAN-Punkt (unten Mitte)
    display_proxy.fill_rect(x + 42, y + 80, 16, 16, 0x00)
    
    # WLAN-Bogen 1 (Klein)
    display_proxy.fill_rect(x + 30, y + 60, 40, 10, 0x00)
    display_proxy.fill_rect(x + 24, y + 64, 10, 10, 0x00) # Kanten abrunden
    display_proxy.fill_rect(x + 66, y + 64, 10, 10, 0x00)
    
    # WLAN-Bogen 2 (Mittel)
    display_proxy.fill_rect(x + 16, y + 40, 68, 10, 0x00)
    display_proxy.fill_rect(x + 8, y + 45, 12, 12, 0x00)
    display_proxy.fill_rect(x + 80, y + 45, 12, 12, 0x00)
    
    # WLAN-Bogen 3 (Groß)
    display_proxy.fill_rect(x + 2, y + 20, 96, 10, 0x00)
    display_proxy.fill_rect(x - 8, y + 26, 14, 14, 0x00)
    display_proxy.fill_rect(x + 94, y + 26, 14, 14, 0x00)
    
    # Das fette X (Durchgestrichen) - 6 Pixel dick
    for i in range(6):
        display_proxy.line(x - 5 + i, y + 10, x + 100 + i, y + 95, 0x00)
        display_proxy.line(x - 5 + i, y + 95, x + 100 + i, y + 10, 0x00)


def draw_icon_steam(x, y):
    """Zeichnet drei aufsteigende Dampf-Schwaden (24x24) -> 'Kaffee kocht'"""
    # Linke Schwade
    display_proxy.fill_rect(x + 4, y + 8, 3, 10, 0x00)
    display_proxy.fill_rect(x + 2, y + 4, 3, 4, 0x00)
    display_proxy.fill_rect(x + 6, y + 18, 3, 4, 0x00)
    
    # Mittlere Schwade (höher angesetzt)
    display_proxy.fill_rect(x + 11, y + 4, 3, 12, 0x00)
    display_proxy.fill_rect(x + 9, y + 0, 3, 4, 0x00)
    display_proxy.fill_rect(x + 13, y + 16, 3, 4, 0x00)
    
    # Rechte Schwade
    display_proxy.fill_rect(x + 18, y + 8, 3, 10, 0x00)
    display_proxy.fill_rect(x + 16, y + 4, 3, 4, 0x00)
    display_proxy.fill_rect(x + 20, y + 18, 3, 4, 0x00)

def draw_large_snowflake(cx, cy):
    """Zeichnet eine massive, ausgestanzte Schneeflocke (50x50) über die Kanne."""
    # 1. Freistellen: Ein weißer Hintergrund-Kasten, der die schwarzen 
    # Füllstands-Balken der Kanne wegradiert, damit die Flocke extrem gut lesbar wird.
    display_proxy.fill_rect(cx - 25, cy - 25, 50, 50, 0xff)
    
    # 2. Zentrale dicke Achsen
    display_proxy.fill_rect(cx - 2, cy - 20, 4, 40, 0x00) # Vertikal
    display_proxy.fill_rect(cx - 20, cy - 2, 40, 4, 0x00) # Horizontal
    
    # 3. Diagonale Äste (durch 5 parallele Linien massiv gemacht)
    for i in range(-2, 3):
        display_proxy.line(cx - 15 + i, cy - 15, cx + 15 + i, cy + 15, 0x00)
        display_proxy.line(cx - 15 + i, cy + 15, cx + 15 + i, cy - 15, 0x00)
        
    # 4. Kristall-Streben an den Enden für den eisigen Look
    display_proxy.fill_rect(cx - 6, cy - 18, 12, 3, 0x00) # Top
    display_proxy.fill_rect(cx - 6, cy + 15, 12, 3, 0x00) # Bottom
    display_proxy.fill_rect(cx - 18, cy - 6, 3, 12, 0x00) # Left
    display_proxy.fill_rect(cx + 15, cy - 6, 3, 12, 0x00) # Right

def draw_icon_battery_low(x, y):
    """Zeichnet eine SCHWARZE, fast leere Batterie (28x16)"""
    # Batterie-Rand (3 Pixel dick, Schwarz)
    for i in range(3):
        display_proxy.rect(x + i, y + i, 28 - 2*i, 16 - 2*i, 0x00)
    # Plus-Pol
    display_proxy.fill_rect(x + 28, y + 4, 3, 8, 0x00)
    # Ein einzelner Balken (fast leer)
    display_proxy.fill_rect(x + 4, y + 4, 5, 8, 0x00)

def update_cups(x, y, cups):
    for i in range(6):
        b_y = (y + 146) - i * 23
        color = 0x00 if i < cups else 0xff
        display_proxy.fill_rect(x + 27, b_y, 56, 18, color)

def draw_tile(tile_x, tile_y, pot):
    """Kachel mit allen dynamischen States, Rahmen und Overlays."""
    w, h = 175, 290 
    
    # --- 1. KACHEL-SCHATTEN (Nur wenn verbunden!) ---
    if pot['conn'] == 0: 
        dither_rect(tile_x + 10, tile_y + 10, w, h)
        
    display_proxy.fill_rect(tile_x, tile_y, w, h, 0xff) 
    display_proxy.rect(tile_x, tile_y, w, h, 0x00)

    # --- 2. KOCH-RAHMEN (Dicker schwarzer Rand) ---
    if pot['state'] == 3:
        for i in range(5):
            display_proxy.rect(tile_x + i, tile_y + i, w - 2*i, h - 2*i, 0x00)

    # --- 3. HAUPTGRAFIK: Kanne oder No-WiFi ---
    if pot['conn'] == 1:
        draw_no_wifi(tile_x + 35, tile_y + 40)
    else:
        carafe_x = tile_x + 20
        carafe_y = tile_y + 20
        draw_severin(carafe_x, carafe_y)
        update_cups(carafe_x, carafe_y, pot['fill'])
        
        # Dynamische Overlays auf der Kanne
        if pot['state'] == 3 and pot['fill'] < 6:
            # Dampf
            steam_x = carafe_x + 43
            steam_y = carafe_y + 146 - (pot['fill'] * 23) - 24
            steam_y = max(steam_y, carafe_y - 12)
            draw_icon_steam(steam_x, steam_y)
            
        elif pot['state'] == 2:
            # Riesige Schneeflocke exakt mittig im Glas-Teil der Kanne
            draw_large_snowflake(carafe_x + 48, carafe_y + 85)
    
    # --- 4. TEXT-BEREICH ---
    display_proxy.hline(tile_x + 10, tile_y + 215, w - 20, 0x00)
    display_proxy.fill_rect(tile_x + 5, tile_y + 225, w - 10, 55, 0xff)
    
    Writer.set_textpos(display_proxy, tile_y + 235, tile_x + 20)
    temp_str = "-- C" if pot['conn'] == 1 else f"{pot['temp']} C"
    text_writer.printstring(temp_str)
    
    # --- 5. STATUS BADGES (Nur noch Batterie) ---
    badge_x = tile_x + 130
    badge_y = tile_y + 240
    
    if pot['batt'] == 0: 
        draw_icon_battery_low(badge_x, badge_y - 22) 

    # --- 6. DAS "DISABLED" OVERLAY ---
    if pot['conn'] == 1:
        for py in range(tile_y + 1, tile_y + h - 1):
            start_x = tile_x + 1 if py % 2 == 0 else tile_x + 2
            for px in range(start_x, tile_x + w - 1, 2):
                display_proxy.pixel(px, py, 0xff)


def update_display(coffee_pots):
    for i, pot in enumerate(coffee_pots):
        x = 15 + i * 195
        # Nur noch Koordinaten und das Dictionary übergeben
        draw_tile(x, 130, pot)


def draw_footer(last_update_time):
    """Footer weiter nach oben versetzt, um den automatischen Scroll-Trigger zu umgehen."""
    # Wir löschen den Bereich von y=430 bis y=470
    display_proxy.fill_rect(0, 455, 800, 35, 0xff) 
    
    Writer.set_textpos(display_proxy, 455, 25)
    text_writer.printstring(f"Letztes Update: {last_update_time}")

def draw_header(time_str, date_str):
    display_proxy.fill_rect(0, 0, 800, 110, 0xff) 
    display_proxy.blit(logo_fb, 20, 20)
    
    Writer.set_textpos(display_proxy, 15, 570)
    clock_writer.printstring(time_str)
    
    Writer.set_textpos(display_proxy, 80, 660)
    text_writer.printstring(date_str)
    
    display_proxy.hline(0, 110, 800, 0x00)

# --- GLOBALE DATEN-ZUSTÄNDE ---
current_hour = 0
current_min = 0
current_day = 1
current_month = 1
current_year = 2026

# Initial-Zustand: 4 Kannen
coffee_pots_data = [{'fill': 0, 'batt': 1, 'state': 0, 'conn': 1, 'temp': 0} for _ in range(4)]
old_alarm_states = [False, False, False, False]

last_ble_rx_ms = time.ticks_ms()
last_minute_tick = time.ticks_ms()
last_update_time = "Niemals"
last_full_refresh = -1
needs_display_update = False


# --- REFRESH LOGIK ---
def do_full_refresh():
    global last_full_refresh

    last_full_refresh = current_min
    print("=> Starte FULL REFRESH...")
    epd.init()
    epd.Clear()
    display_proxy.fill(0xff)
    epd.imagered.fill(0x00)

    time_str = f"{current_hour:02d}:{current_min:02d}"
    date_str = f"{current_day:02d}.{current_month:02d}.{current_year}"
    draw_header(time_str, date_str)
    
    update_display(coffee_pots_data)
    
    draw_footer(last_update_time)
    
    epd.display()
    epd.init_part()
    print("Full Refresh abgeschlossen.")

def do_partial_refresh():
    print("=> Starte PARTIAL REFRESH...")
    for i in range(2):
        # repeat to get rid of stuck black pixels
        epd.display_Partial(epd.buffer_black, 0, 0, 800, 480)
        time.sleep(0.15)
        


# ==========================================
# APPLIKATIONS-SCHLEIFE
# ==========================================
do_full_refresh()

try:
    while True:
        current_time_ms = time.ticks_ms()
        
        # 1. Prüfen, ob NEUE BLE-Daten da sind
        if ble_update_flag:
            ble_update_flag = False
            last_ble_rx_ms = current_time_ms
            last_minute_tick = current_time_ms 
            
            print("\n--- NEUES BLE PAKET EMPFANGEN ---")
            
            # --- DEBUG: RAW HEX DUMP ---
            hex_data = " ".join([f"{b:02X}" for b in new_ble_data])
            print(f"Raw Payload (15 Bytes): {hex_data}")
            
            if len(new_ble_data) < 15:
                print("FEHLER: Paket zu kurz!")
                continue

            # --- PARSING ---
            current_hour  = new_ble_data[0]
            current_min   = new_ble_data[1]
            current_day   = new_ble_data[2]
            current_month = new_ble_data[3]
            current_year  = struct.unpack('<H', new_ble_data[4:6])[0]

            time_str = f"{current_hour:02d}:{current_min:02d}"
            date_str = f"{current_day:02d}.{current_month:02d}.{current_year}"
            last_update_time = f"{date_str} {time_str} Uhr"
            
            n_pots = new_ble_data[6]
            
            print(f"Gelesen -> Zeit: {current_hour:02d}:{current_min:02d} | Datum: {current_day:02d}.{current_month:02d}.{current_year} | Kannen: {n_pots}")
            
            kannen_payload = new_ble_data[7:15]
            coffee_pots_data = []
            
            for i in range(0, 8, 2):
                raw_kann_bytes = kannen_payload[i:i+2]
                val = struct.unpack('<H', raw_kann_bytes)[0]
                
                fill  = (val >> 0) & 0x07
                batt  = (val >> 3) & 0x01
                state = (val >> 4) & 0x03
                conn  = (val >> 6) & 0x01
                temp  = (val >> 7) & 0x7F
                
                print(f"Kanne {i//2 + 1}: Hex={raw_kann_bytes[1]:02X}{raw_kann_bytes[0]:02X} -> Fill={fill}, Temp={temp}°C, State={state}, Conn={conn}")
                
                coffee_pots_data.append({
                    'fill':  fill,
                    'batt':  batt,
                    'state': state,
                    'conn':  conn,
                    'temp':  temp
                })
            
            needs_display_update = True

        # 2. Autonome Uhr: Taktet alle 60 Sekunden weiter (auch ohne BLE)
        elif time.ticks_diff(current_time_ms, last_minute_tick) >= 60000:
            last_minute_tick = current_time_ms
            current_min += 1
            if current_min >= 60:
                current_min = 0
                current_hour = (current_hour + 1) % 24
                
                print(f"Volle Stunde ({current_hour:02d}:00) - Führe Display-Wartung durch!")
                continue
            
            needs_display_update = True
            print(f"Autonomer Minuten-Tick: {current_hour:02d}:{current_min:02d}")

        # 3. Hardware Button (Manuell erzwungener Full-Refresh)
        if manual_refresh_requested:
            manual_refresh_requested = False
            do_full_refresh()
            continue

        # 4. Zentrales Display-Rendering ausführen
        if needs_display_update:
            needs_display_update = False
            
            time_str = f"{current_hour:02d}:{current_min:02d}"
            date_str = f"{current_day:02d}.{current_month:02d}.{current_year}"
            
            # --- ALARM-WECHSEL ERKENNEN ---
            alarm_changed = False
            for i, pot in enumerate(coffee_pots_data):
                current_alarm = (pot['conn'] == 1)
                if current_alarm != old_alarm_states[i]:
                    alarm_changed = True
                    old_alarm_states[i] = current_alarm # Neuen Zustand merken
            
            # --- RENDER ENTSCHEIDUNG ---
            if current_min % 30 == 0 and last_full_refresh != current_min:
                # do_full_refresh to prevent red drift over time
                do_full_refresh()
            else:
                # Normales Update im RAM (Schwarz/Weiß)
                draw_header(time_str, date_str)
                update_display(coffee_pots_data)
                draw_footer(last_update_time)
                
                # Schneller Refresh (Double-Tap)
                do_partial_refresh()
            
        time.sleep(0.1)

except KeyboardInterrupt:
    print("Beendet.")
    epd.sleep()