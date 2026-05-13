// Configuración base
const apiBaseUrl = window.NUTRIAR_API_BASE_URL || window.location.origin;

// Elementos del DOM
const video = document.getElementById('camera-feed');
const canvas = document.getElementById('capture-canvas');
const card = document.getElementById('ar-card');
const riskText = document.getElementById('risk-text');
const cardTitle = document.getElementById('card-title');
const cardBadge = document.getElementById('card-badge');
const statusPill = document.getElementById('status-pill');
const loadingText = document.getElementById('loading-text');
const scanButton = document.getElementById('scan-button');
const metaText = document.getElementById('meta-text');

let cameraStream = null;
let isScanning = false;
let telegramId = null;
let userName = null;

// Inicialización de Telegram WebApp
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
            metaText.textContent = 'Perfil activo: ' + userName;
        } else {
            let user = window.Telegram.WebApp.initDataUnsafe?.user;
            if (user && user.id) {
                telegramId = String(user.id);
                userName = user.first_name || user.username || 'Usuario';
                metaText.textContent = 'Perfil activo: ' + userName;
            } else {
                metaText.textContent = '⚠️ Error: No se pudo cargar perfil. Abre desde Telegram.';
                statusPill.textContent = 'Error Auth';
            }
        }
    }
    // Iniciar cámara al cargar la página
    initCamera();
});

async function initCamera() {
    try {
        statusPill.textContent = 'Iniciando cámara...';
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' },
            audio: false
        });
        video.srcObject = cameraStream;
        statusPill.textContent = 'bot de escaneo';
    } catch (err) {
        statusPill.textContent = 'Sin cámara';
        alert('Por favor permite el acceso a la cámara para escanear etiquetas.');
    }
}

// Nueva función para reiniciar el escaneo (Oculta la tarjeta AR)
function restartScan() {
    card.classList.remove('visible');
    isScanning = false;
    scanButton.classList.remove('scanning-active');
    statusPill.textContent = 'bot de escaneo';
}

// Actualizado para el Mockup: Usar clases CSS en lugar de borrar el ícono
function setLoading(active) {
    if (active) {
        loadingText.classList.add('visible');
        scanButton.classList.add('scanning-active');
    } else {
        loadingText.classList.remove('visible');
        scanButton.classList.remove('scanning-active');
    }
}

// Actualizado para el Mockup: Controla los colores (bg-ok, bg-warning)
function showResult(level, title, message) {
    card.classList.add('visible');
    cardTitle.textContent = title;
    riskText.textContent = message;

    // Limpiar estilos anteriores
    cardBadge.classList.remove('bg-ok', 'bg-warning', 'bg-info');

    if (level === 'ok') {
        cardBadge.textContent = 'APTO';
        cardBadge.classList.add('bg-ok');
        statusPill.textContent = 'Producto seguro';
    } else if (level === 'warning') {
        cardBadge.textContent = 'NO APTO';
        cardBadge.classList.add('bg-warning');
        statusPill.textContent = 'Atención requerida';
    } else {
        cardBadge.textContent = 'ERROR';
        cardBadge.classList.add('bg-info');
        statusPill.textContent = 'Falla de análisis';
    }
}

async function captureFrame() {
    if (!video.videoWidth || !video.videoHeight) throw new Error('Cámara no lista.');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (!blob) reject(new Error('Fallo captura'));
            resolve(blob);
        }, 'image/jpeg', 0.92);
    });
}

// Función principal conectada al botón blanco del HTML
async function startScan() {
    if (isScanning) return;
    if (!telegramId) {
        alert('⚠️ Debes abrir el escáner desde el bot de Telegram (@nutriarbot).');
        return;
    }

    isScanning = true;
    setLoading(true);
    card.classList.remove('visible');
    statusPill.textContent = 'Analizando IA...';

    try {
        const blob = await captureFrame();
        const formData = new FormData();
        formData.append('image', blob, 'scan.jpg');
        formData.append('telegram_id', telegramId);

        const response = await fetch(apiBaseUrl + '/api/analyze', {
            method: 'POST',
            headers: { 'Accept': 'application/json' },
            body: formData
        });

        const data = await response.json();
        
        if (!response.ok || data.status === 'error') throw new Error(data.error);

        const display = data.display || {};
        const level = display.status === 'ok' ? 'ok' : 'warning';
        showResult(level, display.title, display.message);
        
    } catch (err) {
        showResult('info', 'Error de red', err.message || 'No se pudo conectar con el servidor.');
        statusPill.textContent = 'Error';
    } finally {
        setLoading(false);
        isScanning = false;
    }
}