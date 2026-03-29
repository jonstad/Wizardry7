import struct
import re
from pathlib import Path

FILE_PATH = "SAVEGAME.txt"
BLOCK_SIZE = 592

NAME_OFFSET = 0x10
STATS_OFFSET = 0x180

STAT_KEYS = ["STR", "INT", "PIE", "VIT", "DEX", "SPD", "PER", "KAR"]

# Faktiske klasser for dine karakterer
DISPLAY_CLASS = {
    "THESUS": "Fighter",
    "TEMPEST": "Fighter",
    "IDA": "Bard",
    "TOR": "Mage",
    "ADA": "Priest",
    "NOBAL": "Priest",
}

def read_u16(buf, off):
    return struct.unpack_from("<H", buf, off)[0]

def write_u16(buf, off, val):
    struct.pack_into("<H", buf, off, int(val))

def read_u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]

def write_u32(buf, off, val):
    struct.pack_into("<I", buf, off, int(val))

def parse_name(block: bytes) -> str:
    raw = block[NAME_OFFSET:NAME_OFFSET+8]
    return raw.split(b"\x00")[0].decode("ascii", errors="ignore")

def parse_stats(block: bytes) -> dict:
    base = STATS_OFFSET
    return {k: block[base + i] for i, k in enumerate(STAT_KEYS)}

def write_stats(block: bytearray, stats: dict):
    base = STATS_OFFSET
    for i, k in enumerate(STAT_KEYS):
        block[base + i] = int(stats[k])

def detect_hp(block: bytes):
    for i in range(0, len(block) - 3):
        a, b, c, d = block[i:i+4]
        if b != 0 or d != 0:
            continue
        if a == 0 or a > 200:
            continue
        if a != c:
            continue
        return i, a, c
    return None, None, None

def detect_stamina(block: bytes, hp_offset):
    off = hp_offset + 4
    cur = read_u16(block, off)
    maxv = read_u16(block, off + 2)
    if 0 < cur <= maxv <= 200:
        return off, cur, maxv
    return None, None, None

def detect_level(block: bytes, hp_offset):
    off = hp_offset + 0x10
    lvl = read_u16(block, off)
    if 1 <= lvl <= 50:
        return off, lvl
    return None, None

def detect_xp(block: bytes, hp_offset):
    off = hp_offset + 0x14
    xp = read_u32(block, off)
    if xp < 50000000:
        return off, xp
    return None, None

def stats_reasonable(stats: dict) -> bool:
    return all(1 <= v <= 30 for v in stats.values())

def find_character_offsets(data: bytes):
    offsets = []
    for m in re.finditer(rb"[A-Z]{3,8}\x00", data):
        name_offset = m.start()
        block_start = name_offset - NAME_OFFSET
        if block_start < 0:
            continue
        if block_start + BLOCK_SIZE > len(data):
            continue

        block = data[block_start:block_start+BLOCK_SIZE]
        name = parse_name(block)
        if not name or not name.isalpha():
            continue

        stats = parse_stats(block)
        if not stats_reasonable(stats):
            continue

        hp_off, _, _ = detect_hp(block)
        if hp_off is None:
            continue

        offsets.append(block_start)

    return sorted(set(offsets))

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
    write_u16(block, hp_off, hp_cur)
    write_u16(block, hp_off + 2, hp_max)
    write_u16(block, sta_off, sta_cur)
    write_u16(block, sta_off + 2, sta_max)
    write_u16(block, lvl_off, lvl)
    write_u32(block, xp_off, xp)

    buf[off:off+BLOCK_SIZE] = block
    print("\nEndringer lagt inn.\n")

def main():
    path = Path(FILE_PATH)
    data = path.read_bytes()
    buf = bytearray(data)

    offsets = find_character_offsets(data)
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
        edit_character(buf, chars[idx]["offset"])
        chars[idx] = load_char_summary(buf, chars[idx]["offset"])

if __name__ == "__main__":
    main()