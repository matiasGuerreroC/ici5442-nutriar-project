import base64
import json
import os
import socket
import threading
import requests
from datetime import datetime
from html import escape
from io import BytesIO

import telebot
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from groq import Groq
from PIL import Image
from telebot import types
from sqlalchemy.orm import Session

# Importar BD y modelos
from backend.database import SessionLocal, get_db
from backend.models import Usuario, HistorialProducto

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://127.0.0.1:8000/")
PORT = int(os.getenv("PORT", "8000"))
MODELO_VISION = "meta-llama/llama-4-scout-17b-16e-instruct"

if not TELEGRAM_TOKEN:
    raise RuntimeError("Falta TELEGRAM_TOKEN en el archivo .env")

if not GROQ_API_KEY:
    raise RuntimeError("Falta GROQ_API_KEY en el archivo .env")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)
app = FastAPI(title="NutriAR Backend")

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
#perfil_usuario = {
#    "nombre": "Carlos Diabético",
#    "condiciones_medicas": ["Diabetes Tipo 2", "Intolerancia a la Lactosa"],
#    "alergias": ["Ninguna"],
#    "preferencias": ["Cero azúcar añadida", "Sin derivados de la leche"],
#}


def obtener_o_crear_usuario(telegram_id: str, nombre: str = None):
    """Obtiene un usuario de la BD o lo crea si no existe"""
    db = SessionLocal()
    try:
        usuario = db.query(Usuario).filter(Usuario.telegram_id == str(telegram_id)).first()
        if not usuario:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 Registrando nuevo usuario: {nombre}")
            usuario = Usuario(telegram_id=str(telegram_id), nombre=nombre or "Usuario")
            db.add(usuario)
            db.commit()
            db.refresh(usuario)
        
        # 🛠️ LA SOLUCIÓN: "Tocamos" la relación de restricciones.
        # Esto obliga a SQLAlchemy a descargar las alergias y guardarlas 
        # en memoria RAM ANTES de que db.close() corte el internet con Neon.
        _ = usuario.restricciones
        
        return usuario
    finally:
        db.close()

def obtener_prompt_sistema(usuario: Usuario):
    """Genera el System Prompt dinámico leyendo la BD de Neon"""
    
    if usuario and usuario.restricciones:
        # Extraer los nombres de las restricciones reales de la BD
        lista_restricciones =[r.nombre for r in usuario.restricciones]
        contexto_medico = f"ATENCIÓN: El usuario tiene las siguientes condiciones médicas/dietéticas: {', '.join(lista_restricciones)}."
    else:
        contexto_medico = "El usuario no tiene restricciones médicas registradas. Realiza un análisis nutricional general."

    return f"""
    Eres un asistente experto en salud y lectura de etiquetas nutricionales.
    {contexto_medico}
    
    Analiza los ingredientes y la tabla nutricional de la imagen adjunta.
    Cruza la información de la imagen con las condiciones del usuario para determinar si es apto.
    
    DEBES responder ÚNICAMENTE en formato JSON con la siguiente estructura exacta:
    {{
        "es_apto": booleano,
        "ingredientes_peligrosos":["lista", "de", "ingredientes", "que", "hacen", "daño"],
        "razon": "Explicación breve de por qué es o no es apto"
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


def analizar_imagen(image_bytes, usuario: Usuario = None):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️ Procesando imagen...")
    base64_image = procesar_imagen_para_groq(image_bytes)
def analizar_imagen(image_bytes, usuario: Usuario):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️ Procesando imagen...")
    base64_image = procesar_imagen_para_groq(image_bytes)

    # AQUÍ ESTÁ LA MAGIA: Inyectamos el perfil real de la BD
    system_prompt = obtener_prompt_sistema(usuario)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Enviando a Groq con perfil de BD...")
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content":[
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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ ¡Respuesta recibida de Groq!")
    return json.loads(resultado_json)
    # AQUÍ ESTÁ LA MAGIA: Inyectamos al usuario real de la BD
    system_prompt = obtener_prompt_sistema(usuario)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Enviando a Groq con perfil de BD...")
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content":[
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


@app.post("/api/registrar_usuario")
async def registrar_usuario(telegram_id: str, nombre: str = "Usuario"):
    """Endpoint para registrar/obtener usuario desde el WebApp"""
    usuario = obtener_o_crear_usuario(telegram_id=telegram_id, nombre=nombre)
    return {
        "id": usuario.id,
        "telegram_id": usuario.telegram_id,
        "nombre": usuario.nombre,
        "status": "success"
    }


@app.post("/api/analyze")
async def analizar_desde_web(image: UploadFile = File(None), image_base64: str = Form(None), telegram_id: str = Form(None)):
    inicio = datetime.now()
    db = None
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📥 POST /api/analyze recibido")
        
        # 1. OBTENER USUARIO PRIMERO (Para saber sus alergias antes de analizar)
        if not telegram_id:
            return {"error": "Falta telegram_id para identificar al usuario", "status": "error"}
        usuario = obtener_o_crear_usuario(telegram_id=telegram_id)
        
        # 2. PROCESAR IMAGEN Y ANALIZAR CON IA
        if image:
            image_bytes = await image.read()
            datos = analizar_imagen(image_bytes, usuario=usuario)
        elif image_base64:
            if "," in image_base64:
                image_base64 = image_base64.split(",", 1)[1]
            image_bytes = base64.b64decode(image_base64)
            datos = analizar_imagen(image_bytes, usuario=usuario)
        else:
            return {"error": "Debes enviar image o image_base64", "status": "error"}

        # 3. GUARDAR EN EL HISTORIAL (NEON DB)
        db = SessionLocal()
        nuevo_historial = HistorialProducto(
            usuario_id=usuario.id,
            desc_breve_producto="Escaneo desde WebApp",
            es_apto=datos.get("es_apto", False),
            ingredientes_peligrosos=datos.get("ingredientes_peligrosos",[]),
            razon_alerta=datos.get("razon", ""),
            respuesta_json_llm=datos
        )
        db.add(nuevo_historial)
        db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Análisis guardado en BD")

        # 4. RESPONDER AL FRONTEND
        respuesta = construir_respuesta_humana(datos)
        return {"analysis": datos, "display": respuesta, "status": "success"}
        
    except Exception as exc:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {str(exc)}")
        return {"error": str(exc), "status": "error"}
    finally:
        if db:
            db.close()

@bot.message_handler(commands=["start", "help"])
def enviar_bienvenida(message):
    # Registrar/obtener usuario en BD
    usuario = obtener_o_crear_usuario(
        telegram_id=message.from_user.id,
        nombre=message.from_user.first_name or "Usuario"
    )
    
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

    db = None
    try:
        # Obtener/registrar usuario en BD
        usuario = obtener_o_crear_usuario(
            telegram_id=message.from_user.id,
            nombre=message.from_user.first_name or "Usuario"
        )
        
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        datos = analizar_imagen(downloaded_file, usuario=usuario)
        
        # Guardar en historial de BD
        db = SessionLocal()
        nuevo_historial = HistorialProducto(
            usuario_id=usuario.id,
            desc_breve_producto="Escaneo desde Telegram",
            es_apto=datos.get("es_apto", False),
            ingredientes_peligrosos=datos.get("ingredientes_peligrosos", []),
            razon_alerta=datos.get("razon", ""),
            respuesta_json_llm=datos
        )
        db.add(nuevo_historial)
        db.commit()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 💾 Análisis guardado en BD")
        
        respuesta = formatear_respuesta_telegram(datos)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 Formateando respuesta y enviando a Telegram...")
        bot.edit_message_text(respuesta, chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="HTML")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✨ Flujo terminado con éxito.\n")

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ ERROR CRÍTICO: {str(e)}\n")
        bot.edit_message_text(f"❌ Ocurrió un error al procesar la imagen: {str(e)}", chat_id=message.chat.id, message_id=msg_espera.message_id)
    finally:
        if db:
            db.close()


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