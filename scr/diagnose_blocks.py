# diagnose_blocks.py
import struct, sys

def read_str(data, offset, length):
    raw = data[offset:offset+length]
    return raw.split(b"\x00")[0].decode("cp437", errors="replace")

def hexdump(data, off, length=64):
    seg = data[off:off+length]
    return seg.hex(), seg.decode("cp437", errors="replace")

fn = sys.argv[1]
with open(fn, "rb") as f:
    data = f.read()

block_size = 0x180
candidates = []
for off in range(0, len(data)-block_size, 4):
    name = read_str(data, off, 16)
    if not name:
        continue
    cls = data[off + 0x20]
    hp = struct.unpack_from("<h", data, off + 0x30)[0]
    inv_count = data[off + 0x80]
    # samle plausibelhetsinfo
    if cls <= 20 and 0 <= hp <= 500 and inv_count <= 20:
        candidates.append((off, name, cls, hp, inv_count))
        if len(candidates) >= 12:
            break

print("Found candidate blocks:", len(candidates))
for off, name, cls, hp, inv_count in candidates:
    print("----")
    print("offset: 0x%X" % off)
    print("name:", repr(name))
    print("class byte:", cls)
    print("hp:", hp)
    print("inv_count:", inv_count)
    hx, asc = hexdump(data, off, 128)
    print("hex:", hx)
    print("ascii:", asc)
