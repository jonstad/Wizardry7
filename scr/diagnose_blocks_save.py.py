# diagnose_blocks_save.py
import struct, sys, os

def read_str(data, offset, length):
    raw = data[offset:offset+length]
    s = raw.split(b"\x00")[0].decode("cp437", errors="replace")
    return "".join(ch for ch in s if 32 <= ord(ch) <= 126)

def hexdump(data, off, length=64):
    seg = data[off:off+length]
    return seg.hex(), seg.decode("cp437", errors="replace")

# Standardfil (Windows sti). Endre her hvis du vil en annen default.
DEFAULT_PATH = r"C:\GOG Games\Wizardry 7\DSAVANT\savegame.txt"

fn = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
out_fn = "diagnose_output.txt"

if not os.path.exists(fn):
    print(f"Feil: filen finnes ikke: {fn}")
    sys.exit(1)

with open(fn, "rb") as f:
    data = f.read()

with open(out_fn, "w", encoding="utf-8") as out:
    out.write(f"File: {fn}\n")
    out.write(f"Size: {os.path.getsize(fn)}\n\n")

    block_sizes = [0x160, 0x180, 0x1A0, 0x200]
    total_found = 0

    for block_size in block_sizes:
        found = []
        for off in range(0, len(data)-block_size, 4):
            name = read_str(data, off, 16)
            if len(name) < 2:
                continue
            cls = data[off + 0x20] if off + 0x20 < len(data) else 255
            hp = struct.unpack_from("<h", data, off + 0x30)[0] if off + 0x32 < len(data) else -1
            inv_count = data[off + 0x80] if off + 0x80 < len(data) else 255
            if cls <= 20 and 0 <= hp <= 1000 and inv_count <= 30:
                found.append((off, block_size, name, cls, hp, inv_count))
                if len(found) >= 12:
                    break

        out.write(f"Block size 0x{block_size:X}: found {len(found)} candidates\n")
        total_found += len(found)
        for off, bs, name, cls, hp, inv in found:
            out.write("----\n")
            out.write(f"offset: 0x{off:X}   block_size: 0x{bs:X}\n")
            out.write(f"name: {repr(name)}\n")
            out.write(f"class byte: {cls}\n")
            out.write(f"hp: {hp}\n")
            out.write(f"inv_count: {inv}\n")
            hx, asc = hexdump(data, off, 256)
            out.write("hex: " + hx + "\n")
            out.write("ascii: " + asc + "\n\n")

    if total_found == 0:
        out.write("Ingen klare kandidater funnet med standard heuristikk. Viser start av fil:\n")
        hx, asc = hexdump(data, 0, 512)
        out.write("hex: " + hx + "\n")
        out.write("ascii: " + asc + "\n")

print(f"Diagnose ferdig. Output skrevet til {out_fn}")