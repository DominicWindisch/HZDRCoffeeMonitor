import bluetooth
import epd_v2
import machine
import struct
import time
import framebuf
import sprites
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
        if found_data and found_data[0:2] == b'\xfe\xca' and len(found_data) >= 17:
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

def dither_erase_rect(x, y, w, h):
    """Legt ein weißes Schachbrett-Muster über einen Bereich, um schwarze Objekte 'auszugrauen'."""
    for py in range(y, y + h):
        start_x = x if py % 2 == 0 else x + 1
        for px in range(start_x, x + w, 2):
            display_proxy.pixel(px, py, 0xff)

def draw_icon_battery_low(x, y):
    for i in range(3):
        display_proxy.rect(x + i, y + i, 28 - 2*i, 16 - 2*i, 0x00)
    display_proxy.fill_rect(x + 28, y + 4, 3, 8, 0x00)
    display_proxy.fill_rect(x + 4, y + 4, 5, 8, 0x00)

def update_cups(x, y, cups):
    for i in range(6):
        b_y = (y + 146) - i * 23
        color = 0x00 if i < cups else 0xff
        display_proxy.fill_rect(x + 27, b_y, 56, 18, color)

def draw_tile(tile_x, tile_y, pot):
    w, h = 175, 290 
    
    # --- 1. KACHEL-SCHATTEN ---
    if pot['conn'] == 0: 
        dither_rect(tile_x + 10, tile_y + 10, w, h)
        
    display_proxy.fill_rect(tile_x, tile_y, w, h, 0xff) 
    display_proxy.rect(tile_x, tile_y, w, h, 0x00)

    # --- 2. KOCH-RAHMEN ---
    if pot['is_brewing'] == 1 and pot['conn'] == 0:
        for i in range(5):
            display_proxy.rect(tile_x + i, tile_y + i, w - 2*i, h - 2*i, 0x00)

    # --- 3. HAUPTGRAFIK: Sprite Sheet oder No-WiFi ---
    carafe_x = tile_x + 20
    carafe_y = tile_y + 20
    if pot['conn'] == 1:
        fb_nowifi = framebuf.FrameBuffer(bytearray(sprites.no_wifi), 135, 162, framebuf.MONO_HLSB)
        display_proxy.blit(fb_nowifi, carafe_x, carafe_y)
    else:
        # LOGIK: Welche Sprite-Kategorie brauchen wir?
        if pot['is_brewing'] == 1:
            category = 'kocht'
        elif pot['fill'] > 0:
            if pot['steam_level'] == 0:
                category = 'kalt'
            elif pot['steam_level'] == 1:
                category = 'steam1'
            elif pot['steam_level'] == 2:
                category = 'steam2'
            elif pot['steam_level'] == 3:
                category = 'steam3'
            else:
                category = 'fill' # Fallback, falls Dampf-Level unerwartet
        else:
            category = 'fill' # Kanne ist leer
            
        # Den exakten Sprite aus dem generierten Dictionary holen
        # pot['fill'] (0-6) entspricht exakt dem Spalten-Index!
        sprite_data = sprites.sheet[category][pot['fill']]
        
        # Framebuffer erstellen und aufs Display zeichnen
        fb_sprite = framebuf.FrameBuffer(bytearray(sprite_data), 135, 162, framebuf.MONO_HLSB)
        display_proxy.blit(fb_sprite, carafe_x, carafe_y)
    
    # --- 4. TEXT-BEREICH ---
    display_proxy.hline(tile_x + 10, tile_y + 215, w - 20, 0x00)
    display_proxy.fill_rect(tile_x + 5, tile_y + 225, w - 10, 55, 0xff)
    
    Writer.set_textpos(display_proxy, tile_y + 240, tile_x + 20)
    
    if pot['conn'] == 1:
        text_writer.printstring("Offline")
    elif pot['fill'] == 0:
        text_writer.printstring("Leer")
    elif pot['is_brewing'] == 1:
        text_writer.printstring("Kocht...")
    else:
        if pot['age_mins'] == 0:
            text_writer.printstring("Gerade eben")
        elif pot['age_mins'] < 60:
            text_writer.printstring(f"Vor {pot['age_mins']} Min.")
        elif pot['age_mins'] < 120:
            text_writer.printstring("Vor > 1h")
        elif pot['age_mins'] < 180:
            text_writer.printstring("Vor > 2h")
        elif pot['age_mins'] < 240:
            text_writer.printstring("Vor > 3h")
        else:
            text_writer.printstring("Vor > 4h")
    
    # --- 5. STATUS BADGES ---
    badge_x = tile_x + 130
    badge_y = tile_y + 240
    
    if pot['batt'] == 1: # 1 = Low Battery
        draw_icon_battery_low(badge_x, badge_y - 22) 

    # --- 6. DAS "DISABLED" OVERLAY ---
    if pot['conn'] == 1:
        for py in range(tile_y , tile_y + h ):
            start_x = tile_x if py % 2 == 0 else tile_x + 1
            for px in range(start_x, tile_x + w , 2):
                display_proxy.pixel(px, py, 0xff)


def update_display(coffee_pots):
    for i, pot in enumerate(coffee_pots):
        x = 15 + i * 195
        draw_tile(x, 130, pot)

def draw_footer(last_update_text):
    # 1. Den Bereich komplett säubern
    display_proxy.fill_rect(0, 455, 800, 35, 0xff) 
    
    # 2. Text schreiben ("Aktualisiert: DD.MM.YYYY HH MM Uhr")
    Writer.set_textpos(display_proxy, 455, 25)
    text_writer.printstring(f"Aktualisiert: {last_update_text}")
    
    # 3. Manueller kleiner Doppelpunkt für die Uhrzeit
    # X muss den Platz überspringen: "Aktualisiert: 12.12.2026 12 "
    dot_x_small = 312
    display_proxy.fill_rect(dot_x_small, 461, 3, 3, 0x00)
    display_proxy.fill_rect(dot_x_small, 469, 3, 3, 0x00)
    
    # 4. Den Text durch die Schachbrett-Maske zu 50% ausgrauen
    dither_erase_rect(25, 455, 775, 35)

    
def draw_header(time_str_spaced, date_str):
    display_proxy.fill_rect(0, 0, 800, 110, 0xff) 
    display_proxy.blit(logo_fb, 20, 20)
    
    # 1. Große Uhrzeit (mit Leerzeichen!) schreiben
    Writer.set_textpos(display_proxy, 15, 580)
    clock_writer.printstring(time_str_spaced)
    
    # 2. Manueller Doppelpunkt (Mitte der 60px Schrifthöhe)
    dot_x = 676
    display_proxy.fill_rect(dot_x, 30, 10, 10, 0x00) # Oberer Punkt
    display_proxy.fill_rect(dot_x, 50, 10, 10, 0x00) # Unterer Punkt
    
    # Datum (unverändert)
    Writer.set_textpos(display_proxy, 80, 660)
    text_writer.printstring(date_str)
    
    display_proxy.hline(0, 110, 800, 0x00)

# --- GLOBALE DATEN-ZUSTÄNDE ---
current_hour = 0
current_min = 0
current_day = 1
current_month = 1
current_year = 2026

# Initial-Zustand: Neue API
coffee_pots_data = [{'fill': 0, 'batt': 0, 'conn': 1, 'is_brewing': 0, 'steam_level': 0, 'age_mins': 0} for _ in range(4)]
old_alarm_states = [False, False, False, False]

last_ble_rx_ms = time.ticks_ms()
last_minute_tick = time.ticks_ms()
last_update_time = "Niemals"
last_full_refresh = -1
needs_display_update = False
last_processed_payload = b'' # Für den Duplicate Check

# --- REFRESH LOGIK ---
def do_full_refresh():
    global last_full_refresh
    last_full_refresh = current_min
    print("=> Starte FULL REFRESH...")
    epd.init()
    epd.Clear()
    display_proxy.fill(0xff)
    epd.imagered.fill(0x00)

    time_str = f"{current_hour:02d} {current_min:02d}"
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
            
            # --- DUPLICATE CHECK ---
            if new_ble_data == last_processed_payload:
                continue
                
            last_processed_payload = new_ble_data
            last_ble_rx_ms = current_time_ms
            last_minute_tick = current_time_ms 
            
            print("\n--- NEUES BLE PAKET EMPFANGEN ---")
            
            if len(new_ble_data) < 15:
                print("FEHLER: Paket zu kurz!")
                continue

            # --- PARSING ---
            current_hour  = new_ble_data[0]
            current_min   = new_ble_data[1]
            current_day   = new_ble_data[2]
            current_month = new_ble_data[3]
            current_year  = struct.unpack('<H', new_ble_data[4:6])[0]

            # --- 1. SANITY CHECK: ZEIT & DATUM ---
            if not (0 <= current_hour <= 23) or not (0 <= current_min <= 59) or \
               not (1 <= current_day <= 31) or not (1 <= current_month <= 12) or \
               not (2024 <= current_year <= 2100):
                continue

            time_str = f"{current_hour:02d} {current_min:02d}"
            date_str = f"{current_day:02d}.{current_month:02d}.{current_year}"
            
            n_pots = new_ble_data[6]
            if n_pots > 4:
                continue
            
            kannen_payload = new_ble_data[7:15]
            temp_coffee_pots = []
            daten_sind_valide = True
            
            for i in range(0, 8, 2):
                raw_kann_bytes = kannen_payload[i:i+2]
                val = struct.unpack('<H', raw_kann_bytes)[0]
                
                # --- NEUE API MASKEN ---
                fill        = (val >> 0) & 0x07
                batt        = (val >> 3) & 0x01
                conn        = (val >> 4) & 0x01
                is_brewing  = (val >> 5) & 0x01
                steam_level = (val >> 6) & 0x03
                age_mins    = (val >> 8) & 0xFF
                
                # --- 2. SANITY CHECK: KANNEN-WERTE ---
                if fill > 6:
                    print(f"FEHLER: Unplausible Daten Kanne {i//2 + 1}. Paket verworfen!")
                    daten_sind_valide = False
                    break
                
                temp_coffee_pots.append({
                    'fill':        fill,
                    'batt':        batt,
                    'conn':        conn,
                    'is_brewing':  is_brewing,
                    'steam_level': steam_level,
                    'age_mins':    age_mins
                })
            
            # --- 3. ÜBERNAHME DER DATEN ---
            if daten_sind_valide and len(temp_coffee_pots) == 4:
                coffee_pots_data = temp_coffee_pots
                last_update_time = f"{date_str} {time_str} Uhr"
                needs_display_update = True

        # 2. Autonome Uhr: Taktet alle 60 Sekunden weiter
        elif time.ticks_diff(current_time_ms, last_minute_tick) >= 60000:
            last_minute_tick = current_time_ms
            current_min += 1
            if current_min >= 60:
                current_min = 0
                current_hour = (current_hour + 1) % 24
                print(f"Volle Stunde ({current_hour:02d}:00) - Führe Display-Wartung durch!")
                continue
            
            needs_display_update = True

        # 3. Hardware Button
        if manual_refresh_requested:
            manual_refresh_requested = False
            do_full_refresh()
            continue

        # 4. Zentrales Display-Rendering ausführen
        if needs_display_update:
            needs_display_update = False
            
            time_str = f"{current_hour:02d} {current_min:02d}"
            date_str = f"{current_day:02d}.{current_month:02d}.{current_year}"
            
            # --- RENDER ENTSCHEIDUNG ---
            if current_min % 30 == 0 and last_full_refresh != current_min:
                do_full_refresh()
            else:
                draw_header(time_str, date_str)
                update_display(coffee_pots_data)
                draw_footer(last_update_time)
                do_partial_refresh()
            
        time.sleep(0.1)

except KeyboardInterrupt:
    print("Beendet.")
    epd.sleep()