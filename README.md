# NutriAR — Asistente Inteligente en Realidad Aumentada para Análisis Nutricional

**NutriAR** es un sistema de software desacoplado que integra Visión Computacional, Modelos de Lenguaje Multimodales (MLLMs) y Realidad Aumentada (WebAR) para analizar el riesgo nutricional de productos físicos en tiempo real. 

El sistema extrae y procesa los ingredientes de una etiqueta nutricional, cruzando semánticamente esta información con el perfil médico del usuario (ej. celiaquía, alergias, dietas preventivas) para desplegar alertas espaciales deterministas (Apto/No Apto) que reducen la carga cognitiva y mitigan riesgos de salud.

---

## Acceso al Ejecutable (Producción)

Para la revisión de la **Entrega 3**, el sistema se encuentra desplegado y 100% operativo en la nube. Puedes acceder al asistente virtual directamente desde Telegram escaneando el código QR o haciendo clic en el enlace:

**[Iniciar NutriAR en Telegram (@NUTRIAR_ICI5442_BOT)](https://t.me/NUTRIAR_ICI5442_BOT)**

<p align="center">
  <img src="source/qr_nutriar.jpeg" alt="QR NutriAR" width="300"/>
</p>

> **IMPORTANTE: Despertar el Servidor (Cold Start)**
> Dado que el orquestador (Backend) está alojado en la capa gratuita de Render, este entra en "modo reposo" tras 15 minutos sin uso. **Antes de iniciar el bot en Telegram**, por favor haz clic en el siguiente enlace y espera unos 30-50 segundos hasta que la página cargue. Esto "despertará" el servidor y garantizará que los escaneos AR cumplan con la latencia establecida (<5 segundos).
> **[Hacer clic aquí para despertar el Backend](https://nutriar-backend.onrender.com)**

---

## Estado del Proyecto
**Software Final y Validación (Entrega 3) — 100% de Desarrollo.**  
El sistema se encuentra en su versión estable y definitiva (v1.0), con la totalidad de los Casos de Uso y funcionalidades plenamente implementados. Esta versión consolida la arquitectura *End-to-End* (Telegram Mini App servida vía Vercel, orquestación FastAPI en Render, Neon DB y Groq LPU) y cuenta con la validación empírica y análisis estadístico de más de 40 usuarios.

## Stack Tecnológico
*   **Frontend (Capa de Presentación):** HTML5, CSS3, Vanilla JS (Telegram Mini App / Entorno WebAR). Evita frameworks de Virtual DOM para maximizar el rendimiento espacial. Desplegado en **Vercel**.
*   **Backend (Orquestador):** Python 3.10+, FastAPI (ASGI). Desplegado en **Render**.
*   **Base de Datos (Persistencia):** PostgreSQL (Neon Serverless DB) gestionado vía SQLAlchemy.
*   **Core AI (Inferencia Multimodal):** Modelo `llama-4-scout-17b-16e-instruct` ejecutado sobre la infraestructura de hardware LPU de **Groq Cloud**.

## Características Principales
1.  **Enfoque Zero-Install:** Interfaz de usuario accesible directamente a través de un bot de Telegram, sin necesidad de descargar ejecutables (APK/IPA).
2.  **System Prompt Dinámico:** Las restricciones del usuario se persisten en base de datos y se inyectan en tiempo real a las instrucciones de la IA, personalizando cada análisis.
3.  **JSON Mode Estricto:** La IA retorna veredictos forzados a una estructura de datos controlada (`es_apto`, `riesgos`, `razon`), evitando alucinaciones y asegurando la estabilidad del renderizado del frontend.
4.  **Trazabilidad y Contingencia:** Historial persistido de forma nativa en `JSONB` y opción de análisis directo mediante el chat nativo de Telegram como *fallback* si el dispositivo no soporta WebAR.

---

## Estructura del Repositorio (Código Fuente)

```text
ici5442-nutriar-project/
├── bot.py                # Punto de entrada de FastAPI y gestor del bot de Telegram
├── requirements.txt      # Dependencias del proyecto (Backend)
├── source/
│   └── qr_nutriar.jpeg
├── backend/
│   ├── database.py       # Conexión ORM a Neon DB (PostgreSQL)
│   └── models.py         # Modelos de datos y esquemas Pydantic
└── frontend/
    ├── index.html        # Vista WebAR (Escáner de etiquetas)
    ├── historial.html    # Dashboard de trazabilidad
    ├── perfil.html       # Configuración de condiciones médicas
    ├── app.js            # Lógica de cliente, captura de frame y Fetch API
    └── styles.css        # Hoja de estilos de la Mini App
```

---

## Instalación y Configuración (Entorno de Desarrollo Local)

Si desea auditar o ejecutar el código fuente de manera local, siga estas instrucciones:

### 1. Clonar el repositorio
```bash
git clone https://github.com/matiasGuerreroC/ici5442-nutriar-project.git
cd ici5442-nutriar-project
```

### 2. Entorno Virtual
Se recomienda el uso de un entorno virtual para aislar las dependencias.

*Windows:*
```bash
python -m venv venv
venv\Scripts\activate
```
*macOS / Linux:*
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Variables de Entorno
Crea un archivo `.env` en la raíz del proyecto con las siguientes credenciales:

```ini
TELEGRAM_TOKEN="tu_token_del_bot_de_telegram"
GROQ_API_KEY="tu_api_key_de_groq"
WEBAPP_URL="https://tu-url-publica-ngrok.app/"
PORT=8000
DATABASE_URL="postgresql://usuario:password@ep-tu-base-de-datos.region.aws.neon.tech/nutriar_db?sslmode=require"
```

### 5. Ejecución con ngrok (Desarrollo)
Para que Telegram se comunique con el backend local, exponga el puerto mediante un túnel seguro HTTPS:

1. Ejecuta `ngrok http 8000` en una terminal paralela.
2. Copia la URL generada (`https://...`) y actualiza la variable `WEBAPP_URL` en tu `.env`.
3. Inicia el Orquestador:
```bash
python bot.py
```
*(Este comando levanta el servidor FastAPI, sirve el frontend e inicializa la escucha del bot de Telegram).*

---
*Desarrollado para la asignatura Tecnologías Emergentes (ICI5442-2) - Pontificia Universidad Católica de Valparaíso (PUCV).*
