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
const allergensContainer = document.getElementById('allergens-container');

// Variables de Estado Global
let cameraStream = null;
let videoTrack = null; 
let isTorchOn = false; 
let isScanning = false;
let telegramId = null;
let userName = null;


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
            metaText.textContent = userName; // Mostrado en la tarjeta
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
    initCamera();
});

// --- CORRECCIÓN CRÍTICA PARA iOS/TELEGRAM ---
async function initCamera() {
    try {
        statusPill.textContent = 'Iniciando cámara...';
        
        // 1. Pedimos la cámara de la forma más básica y compatible
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' }, // Sin constraints raras aquí
            audio: false
        });
        
        video.srcObject = cameraStream;
        videoTrack = cameraStream.getVideoTracks()[0];
        
        // 2. Asegurarnos de que el video esté listo antes de permitir escanear
        video.onloadedmetadata = () => {
            video.play();
            statusPill.textContent = 'Scanner Activo';
        };
        
        // 3. Revisar la linterna solo de forma segura (Fallback para iOS)
        if (videoTrack.getCapabilities) {
            const capabilities = videoTrack.getCapabilities();
            if (!capabilities.torch && flashlightBtn) {
                flashlightBtn.style.display = 'none'; // Ocultar si no hay linterna
            }
        } else if (flashlightBtn) {
            flashlightBtn.style.display = 'none'; // iOS WebView a veces no expone getCapabilities()
        }
        
    } catch (err) {
        console.error("Error de cámara:", err);
        statusPill.textContent = 'Sin cámara';
        alert('Por favor permite el acceso a la cámara. En iPhone: Ajustes > Telegram > Cámara.');
    }
}


// ==========================================
// 3. CONTROLES Y UI (LINTERNA Y ESTADOS)
// ==========================================
async function toggleFlashlight() {
    if (!videoTrack) return;
    try {
        if (!videoTrack.getCapabilities) return; // Seguridad para iOS
        
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


// ==========================================
// 4. LÓGICA DE LA TARJETA AR (APTO / NO APTO)
// ==========================================
function showResult(level, title, message, ingredients = []) {
    card.classList.add('visible');
    cardTitle.textContent = title;

    // 1. Limpiar estilos anteriores
    cardGlow.classList.remove('alert-glow-danger', 'alert-glow-success', 'alert-glow-info');
    cardBadge.classList.remove('bg-tertiary', 'bg-secondary', 'bg-primary');
    msgIcon.classList.remove('text-tertiary-fixed-dim', 'text-secondary-fixed', 'text-primary-fixed');
    allergensContainer.innerHTML = ''; // Limpiar los "chips" rojos anteriores

    // 2. Aplicar estilos según el resultado
    if (level === 'ok') {
        // --- MODO APTO (VERDE) ---
        cardGlow.classList.add('alert-glow-success');
        cardBadge.classList.add('bg-secondary');
        badgeIcon.textContent = 'verified_user';
        badgeText.textContent = 'SEGURO';
        
        msgIcon.textContent = 'check_circle';
        msgIcon.classList.add('text-secondary-fixed');
        riskText.innerHTML = `<span class="text-secondary-fixed font-bold">Aprobado:</span> ${message}`;
        statusPill.textContent = 'Producto seguro';

    } else if (level === 'warning') {
        // --- MODO PELIGRO (ROJO) ---
        cardGlow.classList.add('alert-glow-danger');
        cardBadge.classList.add('bg-tertiary');
        badgeIcon.textContent = 'warning';
        badgeText.textContent = 'RIESGO';
        
        msgIcon.textContent = 'error';
        msgIcon.classList.add('text-tertiary-fixed-dim');
        riskText.innerHTML = message;
        statusPill.textContent = 'Atención requerida';

        // Dibujar los cuadritos rojos de ingredientes
        if (ingredients && ingredients.length > 0) {
            ingredients.forEach(ing => {
                const chip = document.createElement('div');
                chip.className = 'px-3 py-1 bg-[#ba1a1a]/20 border border-[#ba1a1a]/30 rounded-lg';
                chip.innerHTML = `<p class="text-[11px] font-bold text-white/90">${ing}</p>`;
                allergensContainer.appendChild(chip);
            });
        }

    } else {
        // --- MODO ERROR (AZUL) ---
        cardGlow.classList.add('alert-glow-info');
        cardBadge.classList.add('bg-primary');
        badgeIcon.textContent = 'info';
        badgeText.textContent = 'INFO';
        msgIcon.textContent = 'info';
        msgIcon.classList.add('text-primary-fixed');
        riskText.textContent = message;
    }
}

function restartScan() {
    card.classList.remove('visible');
    isScanning = false;
    scanButton.classList.remove('scanning-active');
    statusPill.textContent = 'Scanner Activo';
    
    // Volvemos a mostrar el mensaje de instrucción
    if (instructionTooltip) {
        instructionTooltip.style.opacity = '1';
    }
}


// ==========================================
// 5. MOTOR DE CAPTURA E INFERENCIA (GROQ API)
// ==========================================
async function captureFrame() {
    // Añadida protección: Si la cámara carga un poco lento, evitamos que crashee.
    if (!video.videoWidth || !video.videoHeight) throw new Error('Cámara inicializando, intenta otra vez.');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (!blob) reject(new Error('Fallo captura'));
            resolve(blob);
        }, 'image/jpeg', 0.85); // Compresión al 85% para mejorar velocidad
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

    // Ocultar Tooltip superior
    if (instructionTooltip) instructionTooltip.style.opacity = '0';

    try {
        // --- FASE 1: Captura de imagen ---
        updateLoadingState(true, 'CAPTURA DE IMAGEN...');
        statusPill.textContent = 'Procesando...';
        
        if (isTorchOn) toggleFlashlight(); 

        const blob = await captureFrame();
        
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

        const response = await fetch(apiBaseUrl + '/api/analyze', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
            body: formData
        });

        clearTimeout(analyzerTimer);

        const data = await response.json();
        
        if (!response.ok || data.status === 'error') throw new Error(data.error);

        const display = data.display || {};
        const level = display.status === 'ok' ? 'ok' : 'warning';
        
        // Extraemos la lista de ingredientes del JSON que devolvió el bot.py
        const ingredientsArray = data.analysis?.ingredientes_peligrosos || [];
        showResult(level, display.title, display.message, ingredientsArray);
        
    } catch (err) {
        showResult('info', 'Error de cámara', err.message || 'No se pudo conectar con el servidor.');
        statusPill.textContent = 'Error';
    } finally {
        updateLoadingState(false);
        isScanning = false;
    }
}