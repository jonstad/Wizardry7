# sjekk_binary.py
import sys, os

fn = sys.argv[1] if len(sys.argv) > 1 else "C:\GOG Games\Wizardry 7\DSAVANT\savegame.txt"
size = os.path.getsize(fn)
with open(fn, "rb") as f:
    head = f.read(128)
print("File:", fn)
print("Size:", size)
print("First 128 bytes (hex):", head[:128].hex())
print("First 128 bytes (ascii):", head[:128].decode("cp437", errors="replace"))

