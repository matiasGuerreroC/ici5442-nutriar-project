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
from backend.models import Usuario, HistorialProducto, Restriccion

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


# --- RESTRICCIONES PREDEFINIDAS ---
RESTRICCIONES_PREDEFINIDAS = {
    "celiaquia": {"nombre": "Celiaquía", "tipo": "condicion_medica"},
    "diabetes": {"nombre": "Diabetes Tipo 2", "tipo": "condicion_medica"},
    "intolerancia_lactosa": {"nombre": "Intolerancia a la Lactosa", "tipo": "condicion_medica"},
    "alergia_mani": {"nombre": "Alergia a Maní", "tipo": "alergia"},
    "alergia_leche": {"nombre": "Alergia a Leche", "tipo": "alergia"},
    "alergia_huevo": {"nombre": "Alergia a Huevo", "tipo": "alergia"},
    "alergia_pescado": {"nombre": "Alergia a Pescado", "tipo": "alergia"},
    "alergia_mariscos": {"nombre": "Alergia a Mariscos", "tipo": "alergia"},
    "alergia_frutos_secos": {"nombre": "Alergia a Frutos Secos", "tipo": "alergia"},
    "sin_azucar": {"nombre": "Preferencia: Sin Azúcar Añadida", "tipo": "preferencia"},
    "sin_gluten": {"nombre": "Preferencia: Sin Gluten", "tipo": "preferencia"},
    "vegano": {"nombre": "Preferencia: Vegano", "tipo": "preferencia"},
    "vegetariano": {"nombre": "Preferencia: Vegetariano", "tipo": "preferencia"},
}


def inicializar_restricciones():
    """Crea las restricciones predefinidas en la BD si no existen"""
    db = SessionLocal()
    try:
        for key, restriccion in RESTRICCIONES_PREDEFINIDAS.items():
            existe = db.query(Restriccion).filter(
                Restriccion.nombre == restriccion["nombre"]
            ).first()
            if not existe:
                nueva = Restriccion(
                    nombre=restriccion["nombre"],
                    tipo=restriccion["tipo"]
                )
                db.add(nueva)
        db.commit()
    except Exception as e:
        print(f"[ERROR] No se pudieron inicializar restricciones: {e}")
    finally:
        db.close()



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


@app.get("/api/restricciones")
async def obtener_restricciones():
    """Obtiene todas las restricciones disponibles agrupadas por tipo"""
    db = SessionLocal()
    try:
        restricciones = db.query(Restriccion).all()
        agrupadas = {
            "condiciones_medicas": [
                {"id": r.id, "nombre": r.nombre}
                for r in restricciones if r.tipo == "condicion_medica"
            ],
            "alergias": [
                {"id": r.id, "nombre": r.nombre}
                for r in restricciones if r.tipo == "alergia"
            ],
            "preferencias": [
                {"id": r.id, "nombre": r.nombre}
                for r in restricciones if r.tipo == "preferencia"
            ],
        }
        return {"status": "success", "restricciones": agrupadas}
    finally:
        db.close()


@app.get("/api/usuario/{telegram_id}")
async def obtener_usuario(telegram_id: str):
    """Obtiene el perfil del usuario y sus restricciones"""
    usuario = obtener_o_crear_usuario(telegram_id=telegram_id)
    db = SessionLocal()
    try:
        restricciones = [
            {"id": r.id, "nombre": r.nombre, "tipo": r.tipo}
            for r in usuario.restricciones
        ]
        return {
            "status": "success",
            "usuario": {
                "id": usuario.id,
                "telegram_id": usuario.telegram_id,
                "nombre": usuario.nombre,
                "fecha_registro": usuario.fecha_registro.isoformat() if usuario.fecha_registro else None,
                "restricciones": restricciones
            }
        }
    finally:
        db.close()


@app.post("/api/usuario/{telegram_id}/restricciones")
async def agregar_restriccion_usuario(telegram_id: str, restriccion_id: int):
    """Agrega una restricción al usuario"""
    db = SessionLocal()
    try:
        usuario = obtener_o_crear_usuario(telegram_id=telegram_id)
        restriccion = db.query(Restriccion).filter(Restriccion.id == restriccion_id).first()
        
        if not restriccion:
            return {"status": "error", "error": "Restricción no encontrada", "codigo": 404}
        
        if restriccion not in usuario.restricciones:
            usuario.restricciones.append(restriccion)
            db.commit()
            return {
                "status": "success",
                "message": f"Restricción '{restriccion.nombre}' agregada",
                "restriccion": {"id": restriccion.id, "nombre": restriccion.nombre}
            }
        else:
            return {
                "status": "error",
                "error": "Esta restricción ya está en tu perfil",
                "codigo": 409
            }
    except Exception as e:
        return {"status": "error", "error": str(e), "codigo": 500}
    finally:
        db.close()


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
    
    db = SessionLocal()
    try:
        # Verificar si el usuario tiene restricciones configuradas
        tiene_restricciones = len(usuario.restricciones) > 0
    finally:
        db.close()
    
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    web_app = types.WebAppInfo(WEBAPP_URL)
    btn_scanner = types.KeyboardButton(text="🚀 Abrir Escáner NutriAR", web_app=web_app)
    btn_perfil = types.KeyboardButton(text="👤 Configurar Perfil")
    
    markup.add(btn_scanner)
    markup.add(btn_perfil)

    if tiene_restricciones:
        mensaje = (
            f"👋 ¡Hola {usuario.nombre}!\n\n"
            f"✓ Tu perfil está configurado.\n\n"
            f"Puedes:\n"
            f"• Usar el <b>Escáner NutriAR</b> para analizar productos\n"
            f"• Enviarme fotos de etiquetas directamente\n"
            f"• Actualizar tu perfil en cualquier momento"
        )
    else:
        mensaje = (
            f"👋 ¡Hola {usuario.nombre}!\n\n"
            f"⚠️ Primero, <b>configura tu perfil</b> con tus restricciones dietéticas y alergias.\n\n"
            f"Así podré personalizarte los análisis de productos."
        )

    bot.reply_to(
        message,
        mensaje,
        reply_markup=markup,
        parse_mode="HTML"
    )


@bot.message_handler(func=lambda message: message.text == "👤 Configurar Perfil")
def boton_perfil(message):
    """Handler para el botón de configurar perfil"""
    configurar_perfil(message)


@bot.message_handler(func=lambda message: message.text == "🚀 Abrir Escáner NutriAR")
def boton_scanner(message):
    """Handler para el botón de escáner"""
    usuario = obtener_o_crear_usuario(
        telegram_id=message.from_user.id,
        nombre=message.from_user.first_name or "Usuario"
    )
    
    db = SessionLocal()
    try:
        tiene_restricciones = len(usuario.restricciones) > 0
    finally:
        db.close()
    
    if not tiene_restricciones:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Configurar ahora", callback_data="ir_perfil"))
        bot.reply_to(
            message,
            "⚠️ Primero configura tu perfil para personalizados análisis.",
            reply_markup=markup
        )
    else:
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        web_app = types.WebAppInfo(WEBAPP_URL)
        btn = types.KeyboardButton(text="🚀 Abrir Escáner NutriAR", web_app=web_app)
        markup.add(btn)
        bot.send_message(
            message.chat.id,
            "🚀 Abriendo escáner...",
            reply_markup=markup
        )


@bot.callback_query_handler(func=lambda call: call.data == "ir_perfil")
def ir_perfil_callback(call):
    """Redirige al usuario al comando /agregar_restriccion"""
    bot.answer_callback_query(call.id)
    agregar_restriccion(call.message)


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


@bot.message_handler(commands=["perfil"])
def configurar_perfil(message):
    """Muestra el perfil actual y permite al usuario agregar/quitar restricciones"""
    db = SessionLocal()
    try:
        usuario = obtener_o_crear_usuario(
            telegram_id=message.from_user.id,
            nombre=message.from_user.first_name or "Usuario"
        )
        
        # Mostrar restricciones actuales
        restricciones = usuario.restricciones
        if restricciones:
            lista_restricciones = "\n".join([f"✓ {r.nombre}" for r in restricciones])
            texto = (
                f"👤 <b>Perfil de {usuario.nombre}</b>\n\n"
                f"<b>Tus restricciones:</b>\n{lista_restricciones}\n\n"
                f"<b>Para agregar más restricciones, usa:</b>\n"
                f"/agregar_restriccion"
            )
        else:
            texto = (
                f"👤 <b>Perfil de {usuario.nombre}</b>\n\n"
                f"Aún no tienes restricciones configuradas.\n\n"
                f"<b>Para agregar tus primeras restricciones, usa:</b>\n"
                f"/agregar_restriccion"
            )
        
        bot.reply_to(message, texto, parse_mode="HTML")
    finally:
        db.close()


@bot.message_handler(commands=["agregar_restriccion"])
def agregar_restriccion(message):
    """Permite al usuario seleccionar restricciones de una lista predefinida"""
    db = SessionLocal()
    try:
        usuario = obtener_o_crear_usuario(
            telegram_id=message.from_user.id,
            nombre=message.from_user.first_name or "Usuario"
        )
        
        # Obtener restricciones disponibles
        todas_restricciones = db.query(Restriccion).all()
        restricciones_usuario = {r.id for r in usuario.restricciones}
        
        # Agrupar por tipo
        condiciones = [r for r in todas_restricciones if r.tipo == "condicion_medica" and r.id not in restricciones_usuario]
        alergias = [r for r in todas_restricciones if r.tipo == "alergia" and r.id not in restricciones_usuario]
        preferencias = [r for r in todas_restricciones if r.tipo == "preferencia" and r.id not in restricciones_usuario]
        
        # Crear teclado interactivo con InlineKeyboardMarkup
        markup = types.InlineKeyboardMarkup(row_width=1)
        
        if condiciones:
            markup.row(types.InlineKeyboardButton("🏥 CONDICIONES MÉDICAS", callback_data="header"))
            for r in condiciones:
                markup.row(types.InlineKeyboardButton(f"✦ {r.nombre}", callback_data=f"add_restriccion_{r.id}"))
        
        if alergias:
            markup.row(types.InlineKeyboardButton("⚠️ ALERGIAS", callback_data="header"))
            for r in alergias:
                markup.row(types.InlineKeyboardButton(f"✦ {r.nombre}", callback_data=f"add_restriccion_{r.id}"))
        
        if preferencias:
            markup.row(types.InlineKeyboardButton("🌱 PREFERENCIAS", callback_data="header"))
            for r in preferencias:
                markup.row(types.InlineKeyboardButton(f"✦ {r.nombre}", callback_data=f"add_restriccion_{r.id}"))
        
        markup.row(types.InlineKeyboardButton("✅ Listo", callback_data="perfil_listo"))
        
        if not condiciones and not alergias and not preferencias:
            bot.reply_to(message, "✅ ¡Ya tienes todas las restricciones disponibles agregadas!")
        else:
            bot.send_message(
                message.chat.id,
                "📋 Selecciona las restricciones que aplican a tu perfil:\n\n"
                "(Puedes seleccionar varias)",
                reply_markup=markup
            )
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data.startswith("add_restriccion_"))
def agregar_restriccion_callback(call):
    """Agrega una restricción al usuario cuando hace clic"""
    db = SessionLocal()
    try:
        restriccion_id = int(call.data.split("_")[-1])
        usuario = obtener_o_crear_usuario(
            telegram_id=call.from_user.id,
            nombre=call.from_user.first_name or "Usuario"
        )
        
        restriccion = db.query(Restriccion).filter(Restriccion.id == restriccion_id).first()
        if restriccion and restriccion not in usuario.restricciones:
            usuario.restricciones.append(restriccion)
            db.commit()
            bot.answer_callback_query(call.id, f"✓ {restriccion.nombre} añadida", show_alert=False)
            # Recargar el mensaje para mostrar la restricción agregada
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=call.message.reply_markup)
        else:
            bot.answer_callback_query(call.id, "Esta restricción ya está en tu perfil", show_alert=False)
    except Exception as e:
        print(f"[ERROR] {e}")
        bot.answer_callback_query(call.id, "Error al agregar restricción", show_alert=True)
    finally:
        db.close()


@bot.callback_query_handler(func=lambda call: call.data == "perfil_listo")
def perfil_listo(call):
    """Finaliza la configuración del perfil"""
    bot.answer_callback_query(call.id)
    bot.edit_message_text(
        "✅ ¡Perfil configurado! Ya puedes usar el escáner con tus restricciones personalizadas.\n\n"
        "🚀 Usa /start para abrir el escáner",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id
    )


@bot.callback_query_handler(func=lambda call: call.data == "header")
def header_callback(call):
    """Ignora los clics en los headers"""
    bot.answer_callback_query(call.id)



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

    print("📋 Inicializando restricciones en BD...")
    inicializar_restricciones()
    
    print("🤖 Bot de NutriAR iniciado. Esperando mensajes...")
    thread_web = threading.Thread(target=iniciar_servidor_web, daemon=True)
    thread_web.start()
    bot.infinity_polling(skip_pending=True)