// ==========================================
// 1. CONFIGURACIÓN BASE Y DOM
// ==========================================
const apiBaseUrl = window.NUTRIAR_API_BASE_URL || window.location.origin;

// Elementos del DOM - Base
const video = document.getElementById('camera-feed');
const canvas = document.getElementById('capture-canvas');
const statusPill = document.getElementById('status-pill');
const metaText = document.getElementById('meta-text');
const instructionTooltip = document.getElementById('instruction-tooltip');

// Elementos del DOM - Controles
const scanButton = document.getElementById('scan-button');
const flashlightBtn = document.getElementById('flashlight-btn');
const flashIcon = document.getElementById('flash-icon');

// Elementos del DOM - Estados de Carga
const loadingContainer = document.getElementById('loading-container');
const loadingMessage = document.getElementById('loading-message');

// Elementos del DOM - NUEVA TARJETA AR
const card = document.getElementById('ar-card');
const cardGlow = document.getElementById('card-glow');
const cardTitle = document.getElementById('card-title');
const riskText = document.getElementById('risk-text');
const cardBadge = document.getElementById('card-badge');
const badgeIcon = document.getElementById('badge-icon');
const badgeText = document.getElementById('badge-text');
const msgIcon = document.getElementById('msg-icon');
const msgContainer = document.getElementById('msg-container');
const allergensContainer = document.getElementById('allergens-container');
const retryButton = document.getElementById('retry-button');
const rescanButton = document.getElementById('rescan-button');

// Variables de Estado Global
let cameraStream = null;
let videoTrack = null; 
let isTorchOn = false; 
let isScanning = false;
let telegramId = null;
let userName = null;
let lastCapturedBlob = null;  // Guardar última imagen para reintentos


// ==========================================
// 2. INICIALIZACIÓN
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const urlTelegramId = urlParams.get('telegram_id');

    if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.ready();
        window.Telegram.WebApp.expand();
        
        if (urlTelegramId) {
            telegramId = String(urlTelegramId);
            const user = window.Telegram.WebApp.initDataUnsafe?.user;
            userName = user ? (user.first_name || user.username || 'Usuario') : 'Usuario';
            metaText.textContent = userName; 
        } else {
            let user = window.Telegram.WebApp.initDataUnsafe?.user;
            if (user && user.id) {
                telegramId = String(user.id);
                userName = user.first_name || user.username || 'Usuario';
                metaText.textContent = userName;
            } else {
                metaText.textContent = 'Modo Web (Sin Perfil)';
                statusPill.textContent = 'Bot no conectado';
            }
        }
    }
});


initCamera();

async function initCamera() {
    try {
        statusPill.textContent = 'Iniciando cámara...';
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' },
            audio: false
        });
        video.srcObject = cameraStream;
        
        // Forzamos la reproducción por si iOS la pauso
        await video.play();
        
        statusPill.textContent = 'Scanner Activo';

        if (cameraStream.getVideoTracks().length > 0) {
            videoTrack = cameraStream.getVideoTracks()[0];
        }

    } catch (err) {
        statusPill.textContent = 'Sin cámara';
        alert('Para usar el escáner, ve a Ajustes del iPhone > Telegram > y activa la cámara.');
    }
}



// ==========================================
// 3. CONTROLES Y UI (LINTERNA Y ESTADOS)
// ==========================================
async function toggleFlashlight() {
    if (!videoTrack) return;
    try {
        if (typeof videoTrack.getCapabilities !== 'function') return; 
        
        const capabilities = videoTrack.getCapabilities();
        if (!capabilities.torch) return; 
        
        isTorchOn = !isTorchOn; 
        
        await videoTrack.applyConstraints({
            advanced: [{ torch: isTorchOn }]
        });
        
        if (isTorchOn) {
            flashIcon.textContent = 'flashlight_off'; 
            flashlightBtn.classList.add('bg-white', 'text-black');
            flashlightBtn.classList.remove('bg-black/40', 'text-white');
        } else {
            flashIcon.textContent = 'flashlight_on';
            flashlightBtn.classList.remove('bg-white', 'text-black');
            flashlightBtn.classList.add('bg-black/40', 'text-white');
        }
    } catch (err) { console.error('Error encendiendo linterna:', err); }
}

function updateLoadingState(active, message = "") {
    if (active) {
        loadingContainer.classList.add('visible');
        scanButton.classList.add('scanning-active');
        if (message) loadingMessage.textContent = message;
    } else {
        loadingContainer.classList.remove('visible');
        scanButton.classList.remove('scanning-active');
    }
}

function restartScan() {
    card.classList.remove('visible');
    isScanning = false;
    scanButton.classList.remove('scanning-active');
    statusPill.textContent = 'Scanner Activo';
    
    // Volvemos a mostrar el mensaje "Enfoca la etiqueta..."
    if (instructionTooltip) {
        instructionTooltip.style.opacity = '1';
    }
}


// ==========================================
// 4. LÓGICA DE LA TARJETA AR (APTO / NO APTO)
// ==========================================
function showResult(level, title, message, ingredients = [], canRetry = false) {
    card.classList.add('visible');
    cardTitle.textContent = title;

    // 1. Limpiar los brillos de la tarjeta principal
    cardGlow.classList.remove('alert-glow-danger', 'alert-glow-success', 'alert-glow-info');
    
    // 2. Limpiar las clases base de la etiqueta (Badge) y la caja de mensaje
    cardBadge.className = 'px-3 py-1 rounded-full flex items-center gap-1.5'; 
    msgContainer.className = 'flex items-start gap-3 p-3 rounded-xl border';
    
    allergensContainer.innerHTML = '';
    
    // Control de botones
    retryButton.style.display = canRetry ? 'flex' : 'none';

    // 3. Aplicar colores vibrantes según el resultado
    if (level === 'ok') {
        // --- MODO APTO (VERDE) ---
        cardGlow.classList.add('alert-glow-success');
        
        // Etiqueta Verde Fuerte
        cardBadge.classList.add('bg-green-600', 'text-white');
        badgeIcon.textContent = 'verified_user';
        badgeText.textContent = 'SEGURO';
        
        // Caja de Explicación Verde Translúcida
        msgContainer.classList.add('bg-green-500/20', 'border-green-500/30');
        msgIcon.textContent = 'check_circle';
        msgIcon.className = 'material-symbols-outlined text-green-400';
        
        riskText.innerHTML = `<span class="text-green-400 font-bold">Aprobado:</span> <span class="text-white/90">${message}</span>`;
        statusPill.textContent = 'Producto seguro';

    } else if (level === 'warning') {
        // --- MODO PELIGRO (ROJO) ---
        cardGlow.classList.add('alert-glow-danger');
        
        // Etiqueta Roja Fuerte
        cardBadge.classList.add('bg-red-600', 'text-white');
        badgeIcon.textContent = 'warning';
        badgeText.textContent = 'RIESGO';
        
        // Caja de Explicación Roja Translúcida
        msgContainer.classList.add('bg-red-500/20', 'border-red-500/30');
        msgIcon.textContent = 'error';
        msgIcon.className = 'material-symbols-outlined text-red-400';
        
        // El texto "Peligro" ya lo envía el bot, así que lo mostramos tal cual
        riskText.innerHTML = `<span class="text-white/90">${message}</span>`;
        statusPill.textContent = 'Atención requerida';

        // Dibujar los cuadritos rojos de ingredientes
        if (ingredients && ingredients.length > 0) {
            ingredients.forEach(ing => {
                const chip = document.createElement('div');
                chip.className = 'px-3 py-1 bg-red-600/40 border border-red-500/50 rounded-lg shadow-sm';
                chip.innerHTML = `<p class="text-[11px] font-bold text-white">${ing}</p>`;
                allergensContainer.appendChild(chip);
            });
        }

    } else {
        // --- MODO ERROR (AZUL) ---
        cardGlow.classList.add('alert-glow-info');
        
        cardBadge.classList.add('bg-blue-600', 'text-white');
        badgeIcon.textContent = 'info';
        badgeText.textContent = 'INFO';
        
        msgContainer.classList.add('bg-blue-500/20', 'border-blue-500/30');
        msgIcon.textContent = 'info';
        msgIcon.className = 'material-symbols-outlined text-blue-400';
        
        riskText.innerHTML = `<span class="text-white/90">${message}</span>`;
        statusPill.textContent = 'Falla de análisis';
    }
}

async function retryLastAnalysis() {
    if (!lastCapturedBlob || !telegramId) {
        alert('Error: No hay imagen para reintentar');
        return;
    }

    isScanning = true;
    card.classList.remove('visible');
    
    try {
        updateLoadingState(true, 'ANALIZANDO INFORMACIÓN...');
        
        const formData = new FormData();
        formData.append('image', lastCapturedBlob, 'scan.jpg');
        formData.append('telegram_id', telegramId);

        const response = await fetch(apiBaseUrl + '/api/analyze', {
            method: 'POST',
            headers: { 
                'Accept': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Error ${response.status}: ${errorText.substring(0, 100)}`);
        }

        const data = await response.json();
        
        if (data.status === 'error') {
            throw new Error(data.error || 'Error del servidor');
        }

        const display = data.display || {};
        const level = display.status === 'ok' ? 'ok' : 'warning';
        const ingredientsArray = data.analysis?.ingredientes_peligrosos || [];
        showResult(level, display.title, display.message, ingredientsArray, false);
        
    } catch (err) {
        console.error("Error en reintento:", err);
        showResult('info', 'Error de red', err.message || 'Por favor, intenta de nuevo.', [], true);
    } finally {
        updateLoadingState(false);
        isScanning = false;
    }
}


// ==========================================
// 5. MOTOR DE CAPTURA E INFERENCIA (GROQ API)
// ==========================================
async function captureFrame() {
    if (!video.videoWidth || !video.videoHeight) throw new Error('Cámara inicializando, intenta otra vez.');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (!blob) reject(new Error('Fallo captura'));
            resolve(blob);
        }, 'image/jpeg', 0.85); 
    });
}

async function startScan() {
    if (isScanning) return;
    if (!telegramId) {
        alert('⚠️ Debes abrir el escáner desde el bot de Telegram (@nutriarbot).');
        return;
    }

    isScanning = true;
    card.classList.remove('visible');

    // Ocultar Tooltip superior de instrucción
    if (instructionTooltip) instructionTooltip.style.opacity = '0';

    try {
        // --- FASE 1: Captura de imagen ---
        updateLoadingState(true, 'CAPTURA DE IMAGEN...');
        statusPill.textContent = 'Procesando...';
        
        if (isTorchOn) toggleFlashlight(); 

        const blob = await captureFrame();
        lastCapturedBlob = blob;  // Guardar para reintentos
        
        const formData = new FormData();
        formData.append('image', blob, 'scan.jpg');
        formData.append('telegram_id', telegramId);

        // --- FASE 2: Enviando datos ---
        await new Promise(resolve => setTimeout(resolve, 500));
        updateLoadingState(true, 'ENVIANDO DATOS...');

        // --- FASE 3: Analizando información ---
        const analyzerTimer = setTimeout(() => {
            if(isScanning) updateLoadingState(true, 'ANALIZANDO INFORMACIÓN...');
        }, 1200);

        // Llama al Backend
        const response = await fetch(apiBaseUrl + '/api/analyze', {
            method: 'POST',
            headers: { 
                'Accept': 'application/json',
                'ngrok-skip-browser-warning': 'true' // Vital para Ngrok
            },
            body: formData,
            timeout: 180000  // 3 minutos timeout
        });

        clearTimeout(analyzerTimer);

        // VERIFICACIÓN DE ERROR CRÍTICA:
        if (!response.ok) {
            const errorText = await response.text();
            console.error("Respuesta fallida del servidor:", errorText);
            throw new Error(`El servidor respondió con código ${response.status}: ${errorText.substring(0, 50)}`);
        }

        const data = await response.json();
        
        if (data.status === 'error') {
            throw new Error(data.error || 'Error desconocido en el servidor.');
        }

        const display = data.display || {};
        const level = display.status === 'ok' ? 'ok' : 'warning';
        
        // Enviar la lista de ingredientes para que se dibujen los cuadritos
        const ingredientsArray = data.analysis?.ingredientes_peligrosos || [];
        showResult(level, display.title, display.message, ingredientsArray, false);
        
    } catch (err) {
        console.error("ERROR CAPTURADO EN EL CATCH:", err);
        // Mostrar error con opción de reintentar (permitir reintentar = true)
        showResult('info', 'Error de conexión', 'Parece que hubo un problema. Intenta nuevamente.', [], true);
        statusPill.textContent = 'Error';
    } finally {
        updateLoadingState(false);
        isScanning = false;
    }
}


// ==========================================
// 6. NAVEGACIÓN ENTRE PANTALLAS
// ==========================================
function goToHistory() {
    if (telegramId) {
        window.location.href = '/historial?telegram_id=' + telegramId;
    } else {
        window.location.href = '/historial';
    }
}

function goToPerfil() {
    if (telegramId) {
        window.location.href = '/perfil?telegram_id=' + telegramId;
    } else {
        window.location.href = '/perfil';
    }
}