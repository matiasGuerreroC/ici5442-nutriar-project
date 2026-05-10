# NutriAR - Prueba de Concepto (Entrega 1)

## Instalación
1. Clonar el repositorio.
2. Crear un entorno virtual: `python -m venv venv` y activarlo.
3. Instalar dependencias: `pip install -r requirements.txt`
4. Crear un archivo `.env` en la raíz con estas variables:
   ```
   TELEGRAM_TOKEN="tu_token"
   GROQ_API_KEY="tu_api_key"
   WEBAPP_URL="https://tu-url-publica/"
   PORT=8000
   DATABASE_URL="NUTRIBASEDB"
   ```

## Ejecución local
1. Ejecutar `python bot.py`.
2. Abrir `http://127.0.0.1:8000/` para probar el escáner AR en el navegador.
3. En Telegram, usar `/start` y abrir el botón del escáner (verá la URL pública).

## Ejecución en macOS
1. Clonar el repositorio.
2. Crear y activar un entorno virtual:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Crear el archivo `.env` en la raíz con las mismas variables que en Windows:
   ```
   TELEGRAM_TOKEN="tu_token"
   GROQ_API_KEY="tu_api_key"
   WEBAPP_URL="https://tu-url-publica/"
   PORT=8000
   ```
5. Ejecutar el bot y backend:
   ```bash
   python bot.py
   ```

## Uso con ngrok en macOS

El flujo en macOS es el mismo que en Windows, pero con comandos de terminal de macOS.

### Paso 1: Instalar ngrok
Opción recomendada con Homebrew:
```bash
brew install ngrok/ngrok/ngrok
```

Si prefieres instalarlo manualmente, descárgalo desde https://ngrok.com/download.

### Paso 2: Ejecutar bot.py localmente
En una terminal:
```bash
python bot.py
```
Eso levanta FastAPI en `http://127.0.0.1:8000`.

### Paso 3: Crear el túnel público
En otra terminal:
```bash
ngrok http 8000
```

Verás una línea parecida a esta:
```text
Forwarding  https://1234-56-789-10-11.ngrok-free.dev -> http://localhost:8000
```

### Paso 4: Actualizar `.env`
Copia la URL HTTPS pública y reemplaza `WEBAPP_URL`:
```text
WEBAPP_URL="https://1234-56-789-10-11.ngrok-free.dev/"
```

### Paso 5: Reiniciar el bot
Detén `python bot.py` con `Ctrl+C` y ejecútalo otra vez para que lea la nueva URL.

### Paso 6: Probar en Telegram
Envía `/start` a tu bot y abre el botón `🚀 Abrir Escáner NutriAR`.

## Uso con ngrok (Para probar desde Telegram)

El bot necesita una URL pública para funcionar en Telegram. **ngrok** crea un túnel HTTPS hacia tu máquina local.

### Paso 1: Instalar ngrok
Descargalo desde https://ngrok.com/download e instálalo en tu `PATH`.

En macOS con Homebrew también puedes usar:
```bash
brew install ngrok/ngrok/ngrok
```

### Paso 2: Ejecutar bot.py localmente
En una terminal:
```bash
python bot.py
```
Esto levantará FastAPI en `http://127.0.0.1:8000`.

### Paso 3: Crear túnel público con ngrok (nuevas terminales)
En otra terminal:
```bash
ngrok http 8000
```
Verás algo como:
```
Forwarding                    https://1234-56-789-10-11.ngrok.io -> http://localhost:8000
```

### Paso 4: Actualizar `.env` con la URL pública
Copia esa URL (por ejemplo `https://1234-56-789-10-11.ngrok.io`) y actualiza tu `.env`:
```
WEBAPP_URL="https://1234-56-789-10-11.ngrok.io/"
```

### Paso 5: Reinicia bot.py
Detén bot.py (Ctrl+C) y vuelve a ejecutarlo:
```bash
python bot.py
```

Ahora el botón en Telegram abrirá la URL pública. Prueba el escáner AR.

## Flujo
- El HTML toma un frame de la cámara y lo envía a `/api/analyze`.
- El backend comprime la imagen, llama a Groq y devuelve JSON estructurado.
- Tanto Telegram como el navegador usan el **mismo endpoint y la misma lógica de análisis**.

## Stack
- **Backend**: FastAPI + Uvicorn
- **Bot**: pyTelegramBotAPI
- **LLM**: Groq (Llama-4-Scout)
- **Frontend**: HTML5 + Canvas + MediaDevices API
- **Túnel**: ngrok