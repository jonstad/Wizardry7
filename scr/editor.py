import json
import re
import struct
from pathlib import Path

FILE_PATH = "SAVEGAME.DBS"
BLOCK_SIZE = 592

NAME_OFFSET = 0x10
STATS_OFFSET = 0x180

STAT_KEYS = ["STR", "INT", "PIE", "VIT", "DEX", "SPD", "PER", "KAR"]

CLASSES = [
    b"FIGHTER", b"MAGE", b"PRIEST", b"BARD", b"THIEF", b"RANGER",
    b"SAMURAI", b"LORD", b"NINJA", b"MONK", b"BISHOP",
    b"ALCHEMIST", b"PSIONIC"
]

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
    return {
        "STR": block[base + 0],
        "INT": block[base + 1],
        "PIE": block[base + 2],
        "VIT": block[base + 3],
        "DEX": block[base + 4],
        "SPD": block[base + 5],
        "PER": block[base + 6],
        "KAR": block[base + 7],
    }

def write_stats(block: bytearray, stats: dict):
    base = STATS_OFFSET
    for i, key in enumerate(STAT_KEYS):
        block[base + i] = int(stats[key])

def detect_hp(block: bytes):
    # search for pattern X 00 X 00
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

def detect_class(block: bytes):
    for cls in CLASSES:
        pos = block.find(cls)
        if pos != -1:
            return cls.decode("ascii")
    return "UNKNOWN"

def stats_reasonable(stats: dict) -> bool:
    vals = list(stats.values())
    if any(v == 0 for v in vals):
        return False
    if any(v > 30 for v in vals):
        return False
    return True

def find_character_offsets(data: bytes):
    pattern = re.compile(rb"([A-Z]{3,8})\x00\x00")
    offsets = []
    seen = set()

    for m in pattern.finditer(data):
        name_offset = m.start(1)
        block_start = name_offset - NAME_OFFSET
        if block_start < 0:
            continue
        if block_start in seen:
            continue
        if block_start + BLOCK_SIZE > len(data):
            continue

        block = data[block_start:block_start+BLOCK_SIZE]
        name = parse_name(block)
        if not name:
            continue
        stats = parse_stats(block)
        if not stats_reasonable(stats):
            continue

        offsets.append(block_start)
        seen.add(block_start)

    return offsets

def load_char_summary(data: bytes, off: int):
    block = data[off:off+BLOCK_SIZE]
    name = parse_name(block)
    stats = parse_stats(block)
    hp_off, hp_cur, hp_max = detect_hp(block)
    cls = detect_class(block)

    return {
        "offset": off,
        "name": name,
        "stats": stats,
        "hp": (hp_cur, hp_max),
        "hp_offset": hp_off,
        "class": cls,
    }

def print_char_summary(idx, ch):
    print(f"[{idx}] {ch['name']} ({ch['class']}): "
          f"HP {ch['hp'][0]}/{ch['hp'][1]}  "
          f"STATS " + " ".join(f"{k}:{ch['stats'][k]}" for k in STAT_KEYS))

def prompt_int(prompt, default=None):
    while True:
        s = input(f"{prompt} [{default}]: " if default is not None else f"{prompt}: ")
        s = s.strip()
        if not s and default is not None:
            return default
        if not s:
            continue
        try:
            return int(s)
        except ValueError:
            print("Ugyldig tall, prøv igjen.")

def edit_character(buf: bytearray, off: int):
    block = bytearray(buf[off:off+BLOCK_SIZE])

    name = parse_name(block)
    stats = parse_stats(block)
    hp_off, hp_cur, hp_max = detect_hp(block)

    print(f"\nRedigerer {name}")
    print("Trykk ENTER for å beholde eksisterende verdi.\n")

    for k in STAT_KEYS:
        stats[k] = prompt_int(f"{k}", stats[k])

    hp_cur = prompt_int("HP current", hp_cur)
    hp_max = prompt_int("HP max", hp_max)

    write_stats(block, stats)
    write_u16(block, hp_off, hp_cur)
    write_u16(block, hp_off + 2, hp_max)

    buf[off:off+BLOCK_SIZE] = block
    print("\nEndringer lagt inn i buffer.\n")

def main():
    path = Path(FILE_PATH)
    data = path.read_bytes()
    buf = bytearray(data)

    offsets = find_character_offsets(data)
    if not offsets:
        print("Fant ingen karakterer i savegame.")
        return

    chars = [load_char_summary(data, off) for off in offsets]

    while True:
        print("\n=== Wizardry 7 CLI Editor ===")
        for i, ch in enumerate(chars):
            print_char_summary(i, ch)
        print("[W] Skriv til fil og avslutt")
        print("[Q] Avslutt uten å skrive\n")

        choice = input("Velg karakterindeks å redigere (eller W/Q): ").strip().upper()
        if choice == "Q":
            print("Avslutter uten å skrive.")
            return
        if choice == "W":
            backup = path.with_suffix(".bak")
            backup.write_bytes(data)
            path.write_bytes(buf)
            print(f"Skrev endringer til {path} (backup: {backup})")
            return

        if not choice.isdigit():
            print("Ugyldig valg.")
            continue

        idx = int(choice)
        if idx < 0 or idx >= len(chars):
            print("Ugyldig indeks.")
            continue

        off = chars[idx]["offset"]
        edit_character(buf, off)

        chars[idx] = load_char_summary(buf, off)

if __name__ == "__main__":
    main()