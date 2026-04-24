import base64
import json
import os
import socket
import threading
from datetime import datetime
from html import escape
from io import BytesIO

import telebot
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from PIL import Image
from telebot import types

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# Cambia esto en bot.py
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://127.0.0.1:8000/") + "?v=2"
PORT = int(os.getenv("PORT", "8000"))
MODELO_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

if not TELEGRAM_TOKEN:
    raise RuntimeError("Falta TELEGRAM_TOKEN en el archivo .env")

if not GROQ_API_KEY:
    raise RuntimeError("Falta GROQ_API_KEY en el archivo .env")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="NutriAR Backend")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurar CORS para permitir requests desde el navegador y Telegram WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PERFIL DE USUARIO ESTÁTICO (Para la PoC) ---
# perfil_usuario = {
#     "nombre": "Juan Pérez",
#     "condiciones_medicas": ["Celiaquía"],
#     "alergias": ["Maní", "Leche"],
#     "preferencias": ["Sin azúcar añadida"]
# }
perfil_usuario = {
    "nombre": "Carlos Diabético",
    "condiciones_medicas": ["Diabetes Tipo 2", "Intolerancia a la Lactosa"],
    "alergias": ["Ninguna"],
    "preferencias": ["Cero azúcar añadida", "Sin derivados de la leche"],
}


def obtener_prompt_sistema():
    return f"""
    Eres un asistente experto en lectura de etiquetas nutricionales.
    Analiza los ingredientes de la imagen considerando las restricciones del usuario: {json.dumps(perfil_usuario, ensure_ascii=False)}.
    DEBES responder ÚNICAMENTE en formato JSON con la siguiente estructura exacta:
    {{
        "es_apto": booleano,
        "ingredientes_peligrosos": ["lista", "de", "ingredientes"],
        "razon": "Explicación muy breve"
    }}
    """


def procesar_imagen_para_groq(image_bytes):
    """
    Comprime la imagen para no superar el límite de 4MB en Base64 que exige Llama-4-Scout.
    """
    img = Image.open(BytesIO(image_bytes))
    img.thumbnail((1024, 1024))

    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{img_str}"


def analizar_imagen(image_bytes):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️ Procesando imagen compartida con el backend web...")
    base64_image = procesar_imagen_para_groq(image_bytes)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Enviando prompt e imagen a la API de Groq (Modelo: {MODELO_VISION})...")
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": obtener_prompt_sistema()},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analiza esta etiqueta y dame el JSON."},
                    {"type": "image_url", "image_url": {"url": base64_image}},
                ],
            },
        ],
        model=MODELO_VISION,
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    resultado_json = chat_completion.choices[0].message.content
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ ¡Respuesta recibida de Groq! JSON Crudo:")
    print("-" * 30)
    print(resultado_json)
    print("-" * 30)

    return json.loads(resultado_json)


def construir_respuesta_humana(datos):
    if datos["es_apto"]:
        return {
            "title": "PRODUCTO APTO",
            "message": "No se detectaron ingredientes que infrinjan tus restricciones.",
            "status": "ok",
        }

    ingredientes_malos = ", ".join(datos.get("ingredientes_peligrosos", [])) or "No especificados"
    razon = datos.get("razon", "")
    texto = f"Peligro: {ingredientes_malos}. {razon}".strip()
    return {
        "title": "PRODUCTO NO APTO",
        "message": texto,
        "status": "warning",
    }


def formatear_respuesta_telegram(datos):
    if datos["es_apto"]:
        return (
            "✅ <b>PRODUCTO APTO</b>\n\n"
            "No se detectaron ingredientes que infrinjan tus restricciones."
        )

    ingredientes_malos = ", ".join(datos.get("ingredientes_peligrosos", [])) or "No especificados"
    razon = datos.get("razon", "No se pudo determinar una razón específica.")
    return (
        "🛑 <b>PRODUCTO NO APTO</b>\n\n"
        f"⚠️ <b>Peligro:</b> {escape(ingredientes_malos)}\n"
        f"📝 <b>Razón:</b> {escape(razon)}"
    )


@app.get("/")
async def servir_index():
    try:
        return FileResponse("index.html", media_type="text/html")
    except Exception as e:
        print(f"[ERROR] No se pudo cargar index.html: {e}")
        raise HTTPException(status_code=500, detail="No se pudo cargar index.html")


@app.get("/api/health")
async def healthcheck():
    return {"status": "ok", "message": "Backend NutriAR activo"}


@app.post("/api/analyze")
async def analizar_desde_web(image: UploadFile = File(None), image_base64: str = Form(None)):
    inicio = datetime.now()
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 POST /api/analyze recibido")
        
        if image:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Leyendo archivo: {image.filename}")
            image_bytes = await image.read()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Bytes recibidos: {len(image_bytes)}")
            
            try:
                datos = analizar_imagen(image_bytes)
            except json.JSONDecodeError as je:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ JSONDecodeError: {str(je)}")
                return {"error": "La LLM no devolvió JSON válido. Intenta de nuevo.", "status": "error"}
                
        elif image_base64:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Base64 recibido, decodificando...")
            if "," in image_base64:
                image_base64 = image_base64.split(",", 1)[1]
            image_bytes = base64.b64decode(image_base64)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 Base64 decodificado, {len(image_bytes)} bytes")
            datos = analizar_imagen(image_bytes)
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Ni archivo ni base64 recibidos")
            return {"error": "Debes enviar un archivo image o image_base64", "status": "error"}

        respuesta = construir_respuesta_humana(datos)
        duracion = (datetime.now() - inicio).total_seconds()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Análisis completado en {duracion:.2f}s, enviando JSON")
        return {"analysis": datos, "display": respuesta, "status": "success"}
        
    except HTTPException as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ HTTPException: {e.detail}")
        raise
    except Exception as exc:
        import traceback
        error_msg = str(exc)
        traceback_str = traceback.format_exc()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error no manejado: {error_msg}")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Traceback:\n{traceback_str}")
        return {"error": f"Error procesando imagen: {error_msg}", "status": "error"}


@bot.message_handler(commands=["start", "help"])
def enviar_bienvenida(message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    web_app = types.WebAppInfo(WEBAPP_URL)
    btn = types.KeyboardButton(text="🚀 Abrir Escáner NutriAR", web_app=web_app)
    markup.add(btn)

    bot.reply_to(
        message,
        "👋 ¡Bienvenido a NutriAR!\n\n"
        "Puedes enviarme una foto para un análisis detallado o "
        "usar el nuevo escáner en Realidad Aumentada.",
        reply_markup=markup,
    )


@bot.message_handler(content_types=["photo"])
def analizar_etiqueta(message):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📸 ¡Foto recibida de {message.from_user.first_name}! Descargando...")
    msg_espera = bot.reply_to(message, "🔍 Analizando etiqueta con Llama-4-Scout en Groq... (Esto tomará un segundo ⚡)")

    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        datos = analizar_imagen(downloaded_file)
        respuesta = formatear_respuesta_telegram(datos)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 Formateando respuesta y enviando a Telegram...")
        bot.edit_message_text(respuesta, chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="HTML")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✨ Flujo terminado con éxito.\n")

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ ERROR CRÍTICO: {str(e)}\n")
        bot.edit_message_text(f"❌ Ocurrió un error al procesar la imagen: {str(e)}", chat_id=message.chat.id, message_id=msg_espera.message_id)


def iniciar_servidor_web():
    import uvicorn
    print(f"🌐 Servidor FastAPI de NutriAR iniciado en http://127.0.0.1:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


def puerto_esta_libre(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.connect_ex(("127.0.0.1", port)) != 0


if __name__ == "__main__":
    if not puerto_esta_libre(PORT):
        raise RuntimeError(
            f"El puerto {PORT} está ocupado. Cierra 'python -m http.server {PORT}' u otro proceso, "
            f"y vuelve a ejecutar 'python bot.py'."
        )

    print("🤖 Bot de NutriAR iniciado. Esperando mensajes...")
    thread_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
    thread_web.start()
    bot.infinity_polling(skip_pending=True)