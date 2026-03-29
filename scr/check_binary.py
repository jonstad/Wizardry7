# sjekk_binary.py
import sys, os

fn = sys.argv[1] if len(sys.argv) > 1 else "C:\GOG Games\Wizardry 7\DSAVANT\savegame.txt"
size = os.path.getsize(fn)
with open(fn, "rb") as f:
    head = f.read(10240)
print("File:", fn)
print("Size:", size)
print("First 64 bytes (hex):", head[:10240].hex())
print("First 64 bytes (ascii):", head[:10240].decode("cp437", errors="replace"))