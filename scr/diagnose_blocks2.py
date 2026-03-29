# diagnose_blocks2.py
import struct, sys, os

def read_str(data, offset, length):
    raw = data[offset:offset+length]
    s = raw.split(b"\x00")[0].decode("cp437", errors="replace")
    return "".join(ch for ch in s if 32 <= ord(ch) <= 126)

def hexdump(data, off, length=64):
    seg = data[off:off+length]
    return seg.hex(), seg.decode("cp437", errors="replace",)

fn = sys.argv[1] if len(sys.argv) > 1 else "C:\GOG Games\Wizardry 7\DSAVANT\savegame.txt"
size = os.path.getsize(fn)
with open(fn, "rb") as f:
    data = f.read()

print("File:", fn)
print("Size:", size)
print()

# prøv flere blokkstørrelser
block_sizes = [0x160, 0x180, 0x1A0, 0x200]
candidates = []

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
            if len(found) >= 8:
                break
    print(f"Block size 0x{block_size:X}: found {len(found)} candidates")
    for off, bs, name, cls, hp, inv in found:
        print("----")
        print(f"offset: 0x{off:X}   block_size: 0x{bs:X}")
        print("name:", repr(name))
        print("class byte:", cls)
        print("hp:", hp)
        print("inv_count:", inv)
        hx, asc = hexdump(data, off, 128)
        print("hex:", hx)
        print("ascii:", asc)
    print()

# hvis ingen kandidater funnet, vis noen tilfeldige hexdumps
if all(len(found)==0 for found in [ [] ]):
    print("Ingen klare kandidater funnet med standard heuristikk. Viser start av fil:")
    hx, asc = hexdump(data, 0, 256)
    print("hex:", hx)
    print("ascii:", asc)