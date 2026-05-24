from PIL import Image
import os

# --- KONFIGURATION ---
IMG_FILE = "spriteSheet.png"
SINGLE_CONN_FILE = "no_connection.png" # Das vergessene Einzelbild
OUT_DIR = "coffee_sprites"
SPRITE_W = 135
SPRITE_H = 162

# Deine Zeilen-Definitionen von oben nach unten
ROW_NAMES = ["fill", "kocht", "kalt", "steam1", "steam2", "steam3"]
COLS = 7

def make_white_transparent(img):
    """Macht den weißen Hintergrund für Home Assistant (Dark Mode) transparent."""
    img = img.convert("RGBA")
    datas = img.getdata()
    new_data = []
    
    for item in datas:
        # Wenn der Pixel weiß (oder sehr hell) ist -> Transparent machen
        if item[0] > 220 and item[1] > 220 and item[2] > 220:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
            
    img.putdata(new_data)
    return img

def process():
    # Ausgabe-Ordner erstellen, falls nicht vorhanden
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)

    # 1. Das große Sprite-Sheet verarbeiten
    if os.path.exists(IMG_FILE):
        print(f"Lade {IMG_FILE} und schneide in Einzelbilder...")
        img = Image.open(IMG_FILE)

        for row_idx, row_name in enumerate(ROW_NAMES):
            for col_idx in range(COLS):
                left = col_idx * SPRITE_W
                top = row_idx * SPRITE_H
                right = left + SPRITE_W
                bottom = top + SPRITE_H

                cropped_img = img.crop((left, top, right, bottom))
                transparent_img = make_white_transparent(cropped_img)

                filename = f"{row_name}_{col_idx}.png"
                filepath = os.path.join(OUT_DIR, filename)
                transparent_img.save(filepath, "PNG")
        print("-> Sprite-Sheet erfolgreich verarbeitet.")
    else:
        print(f"Hinweis: '{IMG_FILE}' nicht im Ordner gefunden, überspringe Gitter.")

    # 2. Das no_connection Einzelbild verarbeiten
    if os.path.exists(SINGLE_CONN_FILE):
        print(f"Verarbeite Einzelbild '{SINGLE_CONN_FILE}'...")
        img_conn = Image.open(SINGLE_CONN_FILE)
        
        # Transparenz hinzufügen
        transparent_conn = make_white_transparent(img_conn)
        
        # Im Zielordner abspeichern
        filepath_conn = os.path.join(OUT_DIR, "no_connection.png")
        transparent_conn.save(filepath_conn, "PNG")
        print("-> 'no_connection.png' erfolgreich mit Transparenz exportiert.")
    else:
        print(f"FEHLER: '{SINGLE_CONN_FILE}' wurde nicht im aktuellen Ordner gefunden!")

    print(f"\nFertig! Alle benötigten Dateien liegen einsatzbereit in '{OUT_DIR}'.")

if __name__ == "__main__":
    process()