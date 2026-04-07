import telebot
import base64
import json
from io import BytesIO
from PIL import Image
from groq import Groq
import os
from dotenv import load_dotenv
from datetime import datetime  # <-- NUEVO: Para ver la hora en los logs

load_dotenv()

# --- CONFIGURACIÓN DE APIS ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = Groq(api_key=GROQ_API_KEY)
MODELO_VISION = "meta-llama/llama-4-scout-17b-16e-instruct" 

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
    "preferencias": ["Cero azúcar añadida", "Sin derivados de la leche"]
}

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

from telebot import types # Importa los tipos para los botones

@bot.message_handler(commands=['start', 'help'])
def enviar_bienvenida(message):
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    
    # IMPORTANTE: Reemplaza la URL con la de tu GitHub Pages o tu tunnel de Ngrok
    # En tu bot.py, dentro de enviar_bienvenida:
    web_app = types.WebAppInfo("https://matiasguerreroc.github.io/ici5442-nutriar-project/")
    
    btn = types.KeyboardButton(text="🚀 Abrir Escáner NutriAR", web_app=web_app)
    markup.add(btn)
    
    bot.reply_to(message, 
                 "👋 ¡Bienvenido a NutriAR!\n\n"
                 "Puedes enviarme una foto para un análisis detallado o "
                 "usar el nuevo escáner en Realidad Aumentada.", 
                 reply_markup=markup)

@bot.message_handler(content_types=['photo'])
def analizar_etiqueta(message):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 📸 ¡Foto recibida de {message.from_user.first_name}! Descargando...")
    msg_espera = bot.reply_to(message, "🔍 Analizando etiqueta con Llama-4-Scout en Groq... (Esto tomará un segundo ⚡)")
    
    try:
        # 1. Obtener la imagen de Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # 2. Comprimir y pasar a Base64
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️ Comprimiendo imagen y convirtiendo a Base64...")
        base64_image = procesar_imagen_para_groq(downloaded_file)
        
        # 3. Armar el Prompt para Llama-4-Scout
        system_prompt = f"""
        Eres un asistente médico experto en lectura de etiquetas nutricionales.
        Analiza los ingredientes de la imagen considerando las restricciones del usuario: {json.dumps(perfil_usuario, ensure_ascii=False)}.
        DEBES responder ÚNICAMENTE en formato JSON con la siguiente estructura exacta:
        {{
            "es_apto": booleano,
            "ingredientes_peligrosos": ["lista", "de", "ingredientes"],
            "razon": "Explicación muy breve"
        }}
        """

        # 4. Llamada a la API de Groq
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Enviando prompt e imagen a la API de Groq (Modelo: {MODELO_VISION})...")
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content":[
                        {"type": "text", "text": "Analiza esta etiqueta y dame el JSON."},
                        {"type": "image_url", "image_url": {"url": base64_image}},
                    ],
                }
            ],
            model=MODELO_VISION,
            response_format={"type": "json_object"}, 
            temperature=0.1 
        )
        
        # 5. Extraer y procesar el JSON
        resultado_json = chat_completion.choices[0].message.content
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ ¡Respuesta recibida de Groq! JSON Crudo:")
        print("-" * 30)
        print(resultado_json) # <-- Aquí verás la magia del JSON estructurado
        print("-" * 30)

        datos = json.loads(resultado_json)
        
        # 6. Formatear la respuesta para el usuario
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 📱 Formateando respuesta y enviando a Telegram...")
        if datos["es_apto"]:
            respuesta = "✅ **PRODUCTO APTO**\n\nNo se detectaron ingredientes que infrinjan tus restricciones."
        else:
            ingredientes_malos = ", ".join(datos["ingredientes_peligrosos"])
            respuesta = f"🛑 **PRODUCTO NO APTO**\n\n⚠️ **Peligro:** {ingredientes_malos}\n📝 **Razón:** {datos['razon']}"
        
        bot.edit_message_text(respuesta, chat_id=message.chat.id, message_id=msg_espera.message_id, parse_mode="Markdown")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✨ Flujo terminado con éxito.\n")

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ ERROR CRÍTICO: {str(e)}\n")
        bot.edit_message_text(f"❌ Ocurrió un error al procesar la imagen: {str(e)}", chat_id=message.chat.id, message_id=msg_espera.message_id)

print("🤖 Bot de NutriAR iniciado. Esperando mensajes...")
bot.polling()