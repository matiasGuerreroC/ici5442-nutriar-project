# NutriAR — Asistente Inteligente en Realidad Aumentada para Análisis Nutricional

**NutriAR** es un sistema de software desacoplado que integra Visión Computacional, Modelos de Lenguaje Multimodales (MLLMs) y Realidad Aumentada (WebAR) para analizar el riesgo nutricional de productos físicos en tiempo real. 

El sistema extrae y procesa los ingredientes de una etiqueta nutricional, cruzando semánticamente esta información con el perfil médico del usuario (ej. celiaquía, alergias, dietas preventivas) para desplegar alertas espaciales deterministas (Apto/No Apto) que reducen la carga cognitiva y mitigan riesgos de salud.

## Estado del Proyecto
**Software Final y Validación (Entrega 3) — 100% de Desarrollo.**  
El sistema se encuentra en su versión estable y definitiva (v1.0), con la totalidad de los Casos de Uso y funcionalidades plenamente implementados. Esta versión consolida la arquitectura *End-to-End* (Telegram Mini App, orquestación FastAPI, Neon DB y Groq LPU).

## Stack Tecnológico
*   **Frontend (Capa de Presentación):** HTML5, CSS3, Vanilla JS (Telegram Mini App / Entorno WebAR). Evita frameworks de Virtual DOM para maximizar el rendimiento espacial.
*   **Backend (Orquestador):** Python 3.10+, FastAPI (ASGI).
*   **Base de Datos (Persistencia):** PostgreSQL (Neon Serverless DB) gestionado vía SQLAlchemy.
*   **Core AI (Inferencia Multimodal):** Modelo `llama-4-scout-17b-16e-instruct` ejecutado sobre la infraestructura de hardware LPU de **Groq Cloud**.

## Características Principales
1.  **Enfoque Zero-Install:** Interfaz de usuario accesible directamente a través de un bot de Telegram, sin necesidad de descargar ejecutables (APK/IPA).
2.  **System Prompt Dinámico:** Las restricciones del usuario se persisten en base de datos y se inyectan en tiempo real a las instrucciones de la IA, personalizando cada análisis.
3.  **JSON Mode Estricto:** La IA retorna veredictos forzados a una estructura de datos controlada (`es_apto`, `riesgos`, `razon`), evitando alucinaciones y asegurando la estabilidad del renderizado del frontend.
4.  **Trazabilidad y Contingencia:** Historial persistido de forma nativa en `JSONB` y opción de análisis directo mediante el chat nativo de Telegram como *fallback* si el dispositivo no soporta WebAR.

---

## Estructura del Repositorio

```text
ici5442-nutriar-project/
├── bot.py                # Punto de entrada de FastAPI y gestor del bot de Telegram
├── requirements.txt      # Dependencias del proyecto (Backend)
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

## Instalación y Configuración Local

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
Crea un archivo `.env` en la raíz del proyecto. Deberás contar con las credenciales de Telegram, Groq y Neon DB:

```ini
TELEGRAM_TOKEN="tu_token_del_bot_de_telegram"
GROQ_API_KEY="tu_api_key_de_groq"
WEBAPP_URL="https://tu-url-publica-ngrok.app/"
PORT=8000
DATABASE_URL="postgresql://usuario:password@ep-tu-base-de-datos.region.aws.neon.tech/nutriar_db?sslmode=require"
```

---

## Ejecución y Pruebas (Uso con ngrok)

Para que Telegram pueda comunicarse con el backend local (FastAPI) y cargar la Mini App, es estrictamente necesario exponer el puerto local a internet mediante un túnel seguro HTTPS.

**1. Levantar el túnel ngrok:**
En una terminal paralela, ejecuta:
```bash
ngrok http 8000
```

**2. Actualizar el Webhook:**
Copia la URL segura `https://...` generada por ngrok, pégala en la variable `WEBAPP_URL` de tu archivo `.env`.

**3. Iniciar el Orquestador (Backend):**
Vuelve a la terminal de tu entorno virtual y ejecuta:
```bash
python bot.py
```
*(Este comando levanta el servidor FastAPI, sirve los archivos estáticos del frontend e inicializa la escucha del bot de Telegram).*

**4. Interactuar:**
Abre Telegram, busca a tu bot y envía el comando `/start`. La aplicación está lista para usarse.

---
*Desarrollado para la asignatura Tecnologías Emergentes (ICI5442-2) - Pontificia Universidad Católica de Valparaíso (PUCV).*