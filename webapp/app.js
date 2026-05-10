const API_BASE = '/api';

const MOCK_NODES = [
    {
        id: 'Sensor:s1',
        temperature: 21.4,
        luminosity: 340,
        barometricPressure: 1013.2,
        humidity: 58,
        accelerationMagnitude: 0.02,
    },
    {
        id: 'Sensor:s2',
        temperature: 19.8,
        luminosity: 120,
        humidity: 62,
        nfcDetected: false,
    },
    {
        id: 'Sensor:s3',
        temperature: 14.1,
        luminosity: 8500,
        barometricPressure: 1012.8,
        bleDevicesNearby: 3,
    },
];

// Utility
function formatDate(isoString) {
    if (!isoString) return '--';
    const date = new Date(isoString);
    return date.toLocaleString('es-ES', { dateStyle: 'short', timeStyle: 'medium' });
}

function updateLastUpdate() {
    const el = document.getElementById('last-update');
    if (el) el.innerText = `Última actualización: ${new Date().toLocaleTimeString()}`;
}

function isNodeOnline(node) {
    const OFFLINE_THRESHOLD = 30 * 60 * 1000; // 30 minutos en milisegundos

    if (!node.temperature) return false;
    if (!node.timestamp) return true; // Si no hay timestamp, asumir que está online

    try {
        const lastUpdate = new Date(node.timestamp).getTime();
        const now = Date.now();
        return (now - lastUpdate) < OFFLINE_THRESHOLD;
    } catch {
        return true; // Si hay error parsing, asumir online
    }
}

// ---------------- Dashboard ----------------
let dashboardNodesData = [];
let selectedNodeId = null;
let viewMode = '3d';
let visibleNodes = new Set();

const NODE_NAMES = { s1: 'Salón', s2: 'Dormitorio', s3: 'Exterior' };
const NODE_COLORS = { s1: '#f59e0b', s2: '#818cf8', s3: '#059669' };

async function fetchNodos() {
    if (!document.getElementById('dashboard-split') && !document.getElementById('all-nodes-view')) return;
    try {
        const res = await fetch(`${API_BASE}/nodos`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        dashboardNodesData = await res.json();
        document.querySelector('.dot').style.backgroundColor = 'var(--success)';
    } catch (e) {
        console.warn('API no disponible, usando datos de prueba:', e.message);
        dashboardNodesData = MOCK_NODES;
        document.getElementById('last-update').innerText = 'Modo demo (sin API)';
        document.querySelector('.dot').style.backgroundColor = 'var(--warning)';
    }

    // Inicializar nodos visibles la primera vez
    if (visibleNodes.size === 0) {
        dashboardNodesData.forEach(n => visibleNodes.add(n.id.replace('Sensor:', '')));
    }

    update3DModel();
    renderNodeSelectorBar();

    if (viewMode === 'cards') {
        renderAllNodes();
    } else {
        if (selectedNodeId) {
            renderNodeDetails(selectedNodeId);
        } else if (dashboardNodesData.find(n => n.id === 'Sensor:s1')) {
            selectNode('s1');
        }
    }

    if (dashboardNodesData !== MOCK_NODES) updateLastUpdate();
}

function selectNode(id) {
    selectedNodeId = `Sensor:${id}`;

    document.querySelectorAll('.room').forEach(el => el.classList.remove('active'));
    const roomEl = document.getElementById(`room-${id}`);
    if (roomEl) roomEl.classList.add('active');
    if (typeof window.highlightRoom3D === 'function') {
        window.highlightRoom3D(id);
    }

    renderNodeDetails(selectedNodeId);
    renderNodeSelectorBar();
}

function setViewMode(mode) {
    viewMode = mode;
    document.getElementById('btn-view-3d').classList.toggle('active', mode === '3d');
    document.getElementById('btn-view-cards').classList.toggle('active', mode === 'cards');

    const split = document.getElementById('dashboard-split');
    const allNodes = document.getElementById('all-nodes-view');
    if (split) split.classList.toggle('hidden', mode === 'cards');
    if (allNodes) allNodes.classList.toggle('hidden', mode !== 'cards');

    renderNodeSelectorBar();
    if (mode === 'cards') renderAllNodes();
}

function renderNodeSelectorBar() {
    const bar = document.getElementById('node-selector-bar');
    if (!bar || dashboardNodesData.length === 0) return;

    if (viewMode === '3d') {
        bar.innerHTML = `<span class="selector-label">Nodo activo:</span>` +
            dashboardNodesData.map(n => {
                const id = n.id.replace('Sensor:', '');
                const name = NODE_NAMES[id] || id;
                const dot = NODE_COLORS[id] || 'var(--accent)';
                const isActive = `Sensor:${id}` === selectedNodeId;
                return `<button class="node-pill ${isActive ? 'active' : ''}" style="${isActive ? `background:${dot};border-color:${dot}` : ''}" onclick="selectNode('${id}')">
                    <span class="np-dot" style="background:${dot}"></span>${name}
                </button>`;
            }).join('');
    } else {
        bar.innerHTML = `<span class="selector-label">Mostrar nodos:</span>` +
            dashboardNodesData.map(n => {
                const id = n.id.replace('Sensor:', '');
                const name = NODE_NAMES[id] || id;
                const dot = NODE_COLORS[id] || 'var(--accent)';
                const isVisible = visibleNodes.has(id);
                return `<button class="node-pill ${isVisible ? 'active' : ''}" style="${isVisible ? `background:${dot};border-color:${dot}` : ''}" onclick="toggleNodeFilter('${id}')">
                    <span class="np-dot" style="background:${isVisible ? 'white' : dot}"></span>${name}
                </button>`;
            }).join('');
    }
}

function toggleNodeFilter(id) {
    if (visibleNodes.has(id)) {
        if (visibleNodes.size > 1) visibleNodes.delete(id);
    } else {
        visibleNodes.add(id);
    }
    renderNodeSelectorBar();
    renderAllNodes();
}

function renderAllNodes() {
    const container = document.getElementById('all-nodes-view');
    if (!container) return;

    const nodes = dashboardNodesData.filter(n => visibleNodes.has(n.id.replace('Sensor:', '')));
    if (nodes.length === 0) {
        container.innerHTML = '<div class="empty-state">Selecciona al menos un nodo para mostrar.</div>';
        return;
    }
    container.innerHTML = `<div class="all-nodes-grid">${nodes.map(renderNodeCard).join('')}</div>`;
}

function renderNodeCard(n) {
    const id = n.id.replace('Sensor:', '');
    const name = NODE_NAMES[id] || id;
    const accentColor = NODE_COLORS[id] || 'var(--accent)';
    const online = isNodeOnline(n);

    let extraHTML = '';
    if (id === 's1') {
        extraHTML = `
            <div class="nc-sensor"><span class="sensor-label">Presión</span><span class="sensor-value">${n.barometricPressure || '--'} hPa</span></div>
            <div class="nc-sensor"><span class="sensor-label">Humedad</span><span class="sensor-value">${n.humidity || '--'} %</span></div>
            <div class="nc-sensor nc-sensor--wide"><span class="sensor-label">Vibración</span><span class="sensor-value">${n.accelerationMagnitude != null ? Number(n.accelerationMagnitude).toFixed(3) : '--'} g</span></div>
        `;
    } else if (id === 's2') {
        extraHTML = `
            <div class="nc-sensor"><span class="sensor-label">Humedad</span><span class="sensor-value">${n.humidity || '--'} %</span></div>
            <div class="nc-sensor"><span class="sensor-label">NFC</span><span class="sensor-value" style="font-size:0.9rem">${n.nfcDetected ? 'Detectado' : 'En espera'}</span></div>
        `;
    } else if (id === 's3') {
        extraHTML = `
            <div class="nc-sensor"><span class="sensor-label">Presión</span><span class="sensor-value">${n.barometricPressure || '--'} hPa</span></div>
            <div class="nc-sensor"><span class="sensor-label">Disp. BLE</span><span class="sensor-value">${n.bleDevicesNearby || '0'}</span></div>
        `;
    }

    return `
        <div class="node-card slide-in" style="--nc-accent:${accentColor}">
            <div class="node-card-accent-bar"></div>
            <div class="card-header" style="padding-bottom:0.75rem; margin-bottom:0.75rem;">
                <div>
                    <h2 class="card-title" style="font-size:1.25rem">${name}</h2>
                    <div style="font-size:0.78rem; color:var(--text-muted); margin-top:0.15rem;">Nodo: ${id}</div>
                </div>
                <span class="badge ${online ? 'good' : 'warn'}">${online ? 'En línea' : 'Sin datos'}</span>
            </div>
            <div class="nc-sensors-grid">
                <div class="nc-sensor"><span class="sensor-label">Temperatura</span><span class="sensor-value">${n.temperature || '--'} °C</span></div>
                <div class="nc-sensor"><span class="sensor-label">Luminosidad</span><span class="sensor-value">${n.luminosity || '--'} lx</span></div>
                ${extraHTML}
            </div>
            <div class="nc-controls">
                <span class="sensor-label" style="display:block; margin-bottom:0.5rem;">Iluminación inteligente</span>
                <div style="display:flex; gap:0.5rem; align-items:center;">
                    <input type="color" id="color-${id}" value="#ffbb00" style="width:52px; height:36px; padding:2px; border-radius:6px; cursor:pointer;" title="Color">
                    <button class="btn-primary" onclick="sendColor('${id}')" style="flex:1; height:36px; font-size:0.8rem;">Aplicar color</button>
                    <button class="btn-secondary" onclick="sendBlink('${id}')" style="height:36px; font-size:0.8rem;">Parpadear</button>
                </div>
            </div>
        </div>
    `;
}

function update3DModel() {
    // We could add status indicators to the 3D model (e.g. red dot if disconnected)
    dashboardNodesData.forEach(n => {
        const shortId = n.id.replace('Sensor:', '');
        const dot = document.querySelector(`#room-${shortId} .node-dot`);
        if (dot) {
            dot.style.backgroundColor = isNodeOnline(n) ? 'var(--success)' : 'var(--warning)';
        }
    });
}

function renderNodeDetails(sensorId) {
    const container = document.getElementById('node-details-panel');
    if (!container) return;
    
    const n = dashboardNodesData.find(node => node.id === sensorId);
    if (!n) {
        container.innerHTML = '<div class="empty-state">No hay datos disponibles para esta zona.</div>';
        return;
    }
    
    const id = n.id.replace('Sensor:', '');
    const name = id === 's1' ? 'Salón' : id === 's2' ? 'Dormitorio' : 'Exterior';
    
    let extraHTML = '';
    if (id === 's1') {
        extraHTML = `
            <div class="sensor-item"><span class="sensor-label">Presión Atmosférica</span><span class="sensor-value">${n.barometricPressure || '--'} hPa</span></div>
            <div class="sensor-item"><span class="sensor-label">Humedad Relativa</span><span class="sensor-value">${n.humidity || '--'} %</span></div>
            <div class="sensor-item"><span class="sensor-label">Vibración (Seguridad)</span><span class="sensor-value">${n.accelerationMagnitude != null ? Number(n.accelerationMagnitude).toFixed(3) : '--'} g</span></div>
        `;
    } else if (id === 's2') {
        extraHTML = `
            <div class="sensor-item"><span class="sensor-label">Humedad Relativa</span><span class="sensor-value">${n.humidity || '--'} %</span></div>
            <div class="sensor-item"><span class="sensor-label">Acceso NFC</span><span class="sensor-value" style="font-size: 1rem; margin-top:4px;">${n.nfcDetected ? 'Tarjeta detectada' : 'A la espera...'}</span></div>
        `;
    } else if (id === 's3') {
        extraHTML = `
            <div class="sensor-item"><span class="sensor-label">Presión Atmosférica</span><span class="sensor-value">${n.barometricPressure || '--'} hPa</span></div>
            <div class="sensor-item"><span class="sensor-label">Dispositivos Cercanos</span><span class="sensor-value">${n.bleDevicesNearby || '0'}</span></div>
        `;
    }

    container.innerHTML = `
        <div class="card detail-card slide-in">
            <div class="card-header">
                <div>
                    <h2 class="card-title" style="font-size: 1.5rem">${name}</h2>
                    <div style="font-size:0.875rem; color:var(--text-muted); margin-top: 0.25rem;">ID de nodo: ${id}</div>
                </div>
                <span class="badge ${isNodeOnline(n) ? 'good' : 'warn'}">${isNodeOnline(n) ? 'En línea' : 'Sin conexión'}</span>
            </div>
            <div class="sensor-grid" style="grid-template-columns: 1fr; gap: 1.5rem;">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    <div class="sensor-item" style="background:#f8fafc; border: 1px solid var(--border-color)">
                        <span class="sensor-label">Temperatura</span>
                        <span class="sensor-value">${n.temperature || '--'} °C</span>
                    </div>
                    <div class="sensor-item" style="background:#f8fafc; border: 1px solid var(--border-color)">
                        <span class="sensor-label">Luminosidad</span>
                        <span class="sensor-value">${n.luminosity || '--'} lx</span>
                    </div>
                </div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                    ${extraHTML.replace(/<div class="sensor-item">/g, '<div class="sensor-item" style="background:#f8fafc; border: 1px solid var(--border-color)">')}
                </div>
            </div>
            <div style="border-top: 1px solid var(--border-color); padding-top: 1.5rem; margin-top: 1.5rem;">
                <span class="sensor-label">Iluminación Inteligente</span>
                <p style="font-size:0.875rem; color:var(--text-muted); margin-bottom: 1rem;">Ajusta el ambiente de color para esta ubicación.</p>
                <div style="display:flex; gap:0.75rem; align-items:center;">
                    <input type="color" id="color-${id}" value="#ffbb00" style="width:80px; height:46px; padding:2px; cursor:pointer;" title="Escoge el color">
                    <button class="btn-primary" onclick="sendColor('${id}')" style="flex:1; height:46px">Aplicar color</button>
                    <button class="btn-secondary" onclick="sendBlink('${id}')" style="height:46px">Parpadear</button>
                </div>
            </div>
        </div>
    `;
}

async function sendColor(nodoId) {
    const hex = document.getElementById(`color-${nodoId}`).value;
    const r = parseInt(hex.substring(1,3), 16);
    const g = parseInt(hex.substring(3,5), 16);
    const b = parseInt(hex.substring(5,7), 16);
    try {
        await fetch(`${API_BASE}/led/${nodoId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({comando: 'color', r, g, b})
        });
    } catch(e) {
        alert('Error al enviar color');
    }
}

async function sendBlink(nodoId) {
    const hex = document.getElementById(`color-${nodoId}`).value;
    const r = parseInt(hex.substring(1,3), 16);
    const g = parseInt(hex.substring(3,5), 16);
    const b = parseInt(hex.substring(5,7), 16);
    try {
        await fetch(`${API_BASE}/led/${nodoId}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({comando: 'parpadear', r, g, b})
        });
    } catch(e) {
        alert('Error al enviar parpadeo');
    }
}

// ---------------- Accesos NFC ----------------
function normalizeUID(uid) {
    const cleaned = uid.toUpperCase().replace(/[^0-9A-F]/g, '');
    if (cleaned.length === 0) return null;
    return cleaned.slice(-4);
}

async function fetchUIDs() {
    if (!document.getElementById('uid-list')) return;
    try {
        const res = await fetch(`${API_BASE}/nfc/uids`);
        const uids = await res.json();
        const container = document.getElementById('uid-list');
        container.innerHTML = '';
        uids.forEach(uid => {
            container.innerHTML += `
                <div class="uid-item">
                    <span style="font-family: monospace; font-weight: 500">${uid}</span>
                    <button class="btn-primary btn-danger btn-sm" onclick="deleteUID('${uid}')">Eliminar</button>
                </div>
            `;
        });
    } catch(e) {
        document.getElementById('uid-list').innerHTML = 'Error al cargar las tarjetas de acceso';
    }
}

async function addUID(uid) {
    const normalized = normalizeUID(uid);
    if (!normalized) {
        alert("UID inválido. Debe contener al menos un carácter hexadecimal (0-9, A-F)");
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/nfc/uids`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid: normalized})
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        document.getElementById('new-uid').value = '';
        fetchUIDs();
    } catch(e) {
        alert("Error al registrar la tarjeta: " + e.message);
    }
}

async function deleteUID(uid) {
    if(!confirm(`¿Revocar acceso a la tarjeta con código ${uid}?`)) return;
    try {
        const res = await fetch(`${API_BASE}/nfc/uids/${uid}`, { method: 'DELETE' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        fetchUIDs();
    } catch(e) {
        alert("Error al revocar la tarjeta: " + e.message);
    }
}

async function fetchAccessLog() {
    if (!document.getElementById('access-log')) return;
    try {
        const res = await fetch(`${API_BASE}/access-log`);
        const logs = await res.json();
        const tbody = document.getElementById('access-log');
        tbody.innerHTML = '';
        if (logs.length === 0) tbody.innerHTML = '<tr><td colspan="4">No hay accesos</td></tr>';
        
        logs.forEach(log => {
            const date = formatDate(log.timestamp);
            const statusBadge = log.authorized ? '<span class="badge good">Autorizado</span>' : '<span class="badge bad">Denegado</span>';
            tbody.innerHTML += `
                <tr>
                    <td>${date}</td>
                    <td style="font-family:monospace">${log.nfcUID}</td>
                    <td>${statusBadge}</td>
                    <td>${log.refSensor}</td>
                </tr>
            `;
        });
    } catch(e) {
        console.error(e);
    }
}

// ---------------- Alertas ----------------
async function fetchAlertas() {
    if (!document.getElementById('alertas-activas')) return;
    try {
        const res = await fetch(`${API_BASE}/alertas`);
        const data = await res.json();

        const activasContainer = document.getElementById('alertas-activas');
        const activas = data.activas || [];
        if (activas.length === 0) {
            activasContainer.innerHTML = '<div class="empty-state">Sin alertas activas</div>';
        } else {
            activasContainer.innerHTML = activas.map(al => {
                const sev = al.severity === 'critical' ? 'bad' : 'warn';
                return `<div class="alerta-activa ${sev}">
                    <span class="alerta-tipo">${al.id.replace('Alert:', '')}</span>
                    <span class="alerta-msg">${al.message || ''}</span>
                    <span class="badge ${sev}">${al.severity || 'warning'}</span>
                </div>`;
            }).join('');
        }

        const tbody = document.getElementById('alertas-historial');
        if (tbody) {
            const historial = data.historial || [];
            tbody.innerHTML = '';
            if (historial.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5">Sin alertas en el historial</td></tr>';
            } else {
                historial.forEach(al => {
                    const date = formatDate(al.timestamp);
                    const sev = al.severity === 'critical' ? 'bad' : al.severity === 'warning' ? 'warn' : 'good';
                    tbody.innerHTML += `<tr>
                        <td>${al.id.replace('Alert:', '')}</td>
                        <td>${date}</td>
                        <td>${al.message || '--'}</td>
                        <td>${al.refSensor || '--'}</td>
                        <td><span class="badge ${sev}">${al.severity || 'info'}</span></td>
                    </tr>`;
                });
            }
        }

        updateLastUpdate();
    } catch(e) {
        console.error(e);
    }
}

// ---------------- Mobile Sidebar ----------------
function toggleSidebar() {
    document.body.classList.toggle('sidebar-open');
}

function closeSidebar() {
    document.body.classList.remove('sidebar-open');
}

// Close sidebar when a nav link is clicked on mobile
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.sidebar a').forEach(a => {
        a.addEventListener('click', closeSidebar);
    });
    // Close on resize to desktop
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768) closeSidebar();
    });
});

// ---------------- Estado ----------------
async function fetchStatus() {
    if (!document.getElementById('api-status')) return;
    try {
        const res = await fetch(`${API_BASE}/status`);
        const status = await res.json();
        
        document.getElementById('api-status').innerText = 'Online';
        document.getElementById('orion-url').innerText = status.orion;
        document.getElementById('ttn-app').innerText = status.ttn_app;
        
        const ttnBadge = document.getElementById('ttn-key-status');
        if (status.ttn_ready) {
            ttnBadge.innerText = 'Configurada';
            ttnBadge.className = 'value badge good';
        } else {
            ttnBadge.innerText = 'Falta API Key';
            ttnBadge.className = 'value badge bad';
        }
        
        document.getElementById('status-time').innerText = formatDate(status.timestamp);
    } catch(e) {
        const badge = document.getElementById('api-status');
        badge.innerText = 'Offline';
        badge.className = 'value badge bad';
    }
}
