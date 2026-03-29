#!/usr/bin/env python3
# improved_wiz7_editor.py
# Forbedret versjon basert på brukerens skript

import struct
import re
from pathlib import Path

# ---------- Konfigurasjon ----------
DEFAULT_FILE = r"C:\GOG Games\Wizardry 7\DSAVANT\savegame.txt"
# blokkstørrelse du fant: 592 decimal = 0x250
BLOCK_SIZE = 592

NAME_OFFSET = 0x10
STATS_OFFSET = 0x180

STAT_KEYS = ["STR", "INT", "PIE", "VIT", "DEX", "SPD", "PER", "KAR"]

DISPLAY_CLASS = {
    "THESUS": "Fighter",
    "TEMPEST": "Fighter",
    "IDA": "Bard",
    "TOR": "Mage",
    "ADA": "Priest",
    "NOBAL": "Priest",
}

# ---------- Trygge lese-/skrivefunksjoner ----------
def safe_unpack_from(fmt, buf, off):
    size = struct.calcsize(fmt)
    if off < 0 or off + size > len(buf):
        raise IndexError("Out of bounds unpack")
    return struct.unpack_from(fmt, buf, off)

def read_u16(buf, off):
    try:
        return safe_unpack_from("<H", buf, off)[0]
    except Exception:
        return 0

def write_u16(buf, off, val):
    struct.pack_into("<H", buf, off, int(val))

def read_u32(buf, off):
    try:
        return safe_unpack_from("<I", buf, off)[0]
    except Exception:
        return 0

def write_u32(buf, off, val):
    struct.pack_into("<I", buf, off, int(val))

# ---------- Tekst/strenghåndtering (DOS CP437) ----------
def parse_name(block: bytes) -> str:
    raw = block[NAME_OFFSET:NAME_OFFSET+8]
    s = raw.split(b"\x00")[0].decode("cp437", errors="replace")
    # behold kun synlige ASCII‑tegn for stabil visning
    s = "".join(ch for ch in s if 32 <= ord(ch) <= 126)
    return s

# ---------- Stats ----------
def parse_stats(block: bytes) -> dict:
    base = STATS_OFFSET
    stats = {}
    for i, k in enumerate(STAT_KEYS):
        off = base + i
        stats[k] = block[off] if off < len(block) else 0
    return stats

def write_stats(block: bytearray, stats: dict):
    base = STATS_OFFSET
    for i, k in enumerate(STAT_KEYS):
        off = base + i
        if off < len(block):
            block[off] = int(stats[k])

def stats_reasonable(stats: dict) -> bool:
    # aksepter litt bredere range for å være tolerant mot variasjoner
    return all(1 <= v <= 255 for v in stats.values())

# ---------- HP / Stamina / Level / XP deteksjon ----------
def detect_hp(block: bytes):
    """
    Søk etter plausibel 16bit current/max par i blokken.
    Returnerer (offset, cur, max) eller (None, None, None).
    Vi ser etter cur<=max, begge <= 65535, og cur>0.
    Prioriter par der max <= 9999 og cur <= max.
    """
    best = (None, None, None)
    for i in range(0, len(block) - 3):
        try:
            cur = read_u16(block, i)
            mx = read_u16(block, i + 2)
        except Exception:
            continue
        if 0 < cur <= mx and mx <= 9999:
            # heuristikk: foretrekk lavere offset nær STATS_OFFSET
            if best[0] is None:
                best = (i, cur, mx)
            else:
                # velg den som ligger nærmere STATS_OFFSET
                if abs(i - STATS_OFFSET) < abs(best[0] - STATS_OFFSET):
                    best = (i, cur, mx)
    return best

def detect_stamina(block: bytes, hp_offset):
    # ofte rett etter HP (hp_offset + 4), men vi søker et par i nærheten
    if hp_offset is None:
        return (None, None, None)
    start = max(0, hp_offset + 2)
    end = min(len(block) - 3, hp_offset + 0x40)
    for i in range(start, end):
        cur = read_u16(block, i)
        mx = read_u16(block, i + 2)
        if 0 <= cur <= mx and mx <= 9999:
            return (i, cur, mx)
    return (None, None, None)

def detect_level(block: bytes, hp_offset):
    # level er ofte et 16bit ved et fast offset fra HP; prøv hp_offset + 0x10 og søk i nærheten
    candidates = []
    if hp_offset is None:
        return (None, None)
    for i in range(max(0, hp_offset + 8), min(len(block) - 1, hp_offset + 0x30)):
        lvl = read_u16(block, i)
        if 1 <= lvl <= 99:
            candidates.append((i, lvl))
    if not candidates:
        return (None, None)
    # velg kandidat nærmest hp_offset+0x10
    target = hp_offset + 0x10
    best = min(candidates, key=lambda x: abs(x[0] - target))
    return best

def detect_xp(block: bytes, hp_offset):
    # XP er ofte 32bit rett etter level; søk i området
    if hp_offset is None:
        return (None, None)
    for i in range(max(0, hp_offset + 0x10), min(len(block) - 3, hp_offset + 0x60)):
        xp = read_u32(block, i)
        if 0 <= xp < 50000000:
            return (i, xp)
    return (None, None)

# ---------- Finn karakterblokker ----------
def find_character_offsets(data: bytes):
    offsets = []
    # søk etter mulige navn: 3–8 store bokstaver, eller alfanumerisk DOS‑navn
    for m in re.finditer(rb"[A-Z0-9]{3,8}\x00", data):
        name_offset = m.start()
        block_start = name_offset - NAME_OFFSET
        if block_start < 0:
            continue
        if block_start + BLOCK_SIZE > len(data):
            continue
        block = data[block_start:block_start+BLOCK_SIZE]
        name = parse_name(block)
        if not name or not name.isalnum():
            continue
        stats = parse_stats(block)
        if not stats_reasonable(stats):
            continue
        hp_off, hp_cur, hp_max = detect_hp(block)
        if hp_off is None:
            continue
        # enkel plausibilitetskontroll: level og xp må finnes
        lvl_off, lvl = detect_level(block, hp_off)
        xp_off, xp = detect_xp(block, hp_off)
        if lvl_off is None or xp_off is None:
            # aksepter likevel hvis stats og hp ser veldig plausible ut
            pass
        offsets.append(block_start)
    return sorted(set(offsets))

# ---------- Last inn og oppsummer ----------
def load_char_summary(data: bytes, off: int):
    block = data[off:off+BLOCK_SIZE]
    name = parse_name(block)
    stats = parse_stats(block)
    hp_off, hp_cur, hp_max = detect_hp(block)
    sta_off, sta_cur, sta_max = detect_stamina(block, hp_off)
    lvl_off, lvl = detect_level(block, hp_off)
    xp_off, xp = detect_xp(block, hp_off)
    cls = DISPLAY_CLASS.get(name, "UNKNOWN")
    return {
        "offset": off,
        "name": name,
        "stats": stats,
        "class": cls,
        "hp": (hp_cur, hp_max),
        "hp_offset": hp_off,
        "stamina": (sta_cur, sta_max),
        "stamina_offset": sta_off,
        "level": lvl,
        "level_offset": lvl_off,
        "xp": xp,
        "xp_offset": xp_off,
    }

def print_char_summary(idx, ch):
    print(f"[{idx}] {ch['name']} ({ch['class']}): "
          f"LV {ch['level']}  "
          f"HP {ch['hp'][0]}/{ch['hp'][1]}  "
          f"STA {ch['stamina'][0]}/{ch['stamina'][1]}  "
          f"XP {ch['xp']}  "
          f"STATS " + " ".join(f"{k}:{ch['stats'][k]}" for k in STAT_KEYS))

# ---------- Interaktiv redigering ----------
def prompt_int(prompt, default=None):
    while True:
        s = input(f"{prompt} [{default}]: ").strip()
        if not s and default is not None:
            return default
        try:
            return int(s)
        except ValueError:
            print("Ugyldig tall.")

def edit_character(buf: bytearray, off: int):
    block = bytearray(buf[off:off+BLOCK_SIZE])
    name = parse_name(block)
    stats = parse_stats(block)
    hp_off, hp_cur, hp_max = detect_hp(block)
    sta_off, sta_cur, sta_max = detect_stamina(block, hp_off)
    lvl_off, lvl = detect_level(block, hp_off)
    xp_off, xp = detect_xp(block, hp_off)
    print(f"\nRedigerer {name}\n")
    for k in STAT_KEYS:
        stats[k] = prompt_int(k, stats[k])
    hp_cur = prompt_int("HP current", hp_cur)
    hp_max = prompt_int("HP max", hp_max)
    sta_cur = prompt_int("Stamina current", sta_cur)
    sta_max = prompt_int("Stamina max", sta_max)
    lvl = prompt_int("Level", lvl)
    xp = prompt_int("XP", xp)
    write_stats(block, stats)
    if hp_off is not None:
        write_u16(block, hp_off, hp_cur)
        write_u16(block, hp_off + 2, hp_max)
    if sta_off is not None:
        write_u16(block, sta_off, sta_cur)
        write_u16(block, sta_off + 2, sta_max)
    if lvl_off is not None:
        write_u16(block, lvl_off, lvl)
    if xp_off is not None:
        write_u32(block, xp_off, xp)
    buf[off:off+BLOCK_SIZE] = block
    print("\nEndringer lagt inn.\n")

# ---------- CLI / main ----------
def main():
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DEFAULT_FILE)
    if not path.exists():
        print("Finner ikke fil:", path)
        return
    data = path.read_bytes()
    buf = bytearray(data)
    offsets = find_character_offsets(data)
    if not offsets:
        print("Fant ingen karakterblokker med standard heuristikk.")
        print("Tips: prøv å peke direkte på den rå savefila (ikke container), eller gi meg diagnose_output.")
        return
    chars = [load_char_summary(data, off) for off in offsets]
    while True:
        print("\n=== Wizardry 7 CLI Editor ===")
        for i, ch in enumerate(chars):
            print_char_summary(i, ch)
        print("[W] Skriv til fil og avslutt")
        print("[Q] Avslutt uten å skrive\n")
        choice = input("Valg: ").strip().upper()
        if choice == "Q":
            return
        if choice == "W":
            path.with_suffix(".bak").write_bytes(data)
            path.write_bytes(buf)
            print("Lagret.")
            return
        if not choice.isdigit():
            continue
        idx = int(choice)
        if idx < 0 or idx >= len(chars):
            print("Ugyldig indeks.")
            continue
        edit_character(buf, chars[idx]["offset"])
        # oppdater summary fra buf
        chars[idx] = load_char_summary(buf, chars[idx]["offset"])

if __name__ == "__main__":
    main()