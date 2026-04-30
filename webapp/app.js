const API_BASE = '/api';

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

// ---------------- Dashboard ----------------
let dashboardNodesData = [];
let selectedNodeId = null;

async function fetchNodos() {
    if (!document.getElementById('dashboard-split')) return;
    try {
        const res = await fetch(`${API_BASE}/nodos`);
        dashboardNodesData = await res.json();
        
        update3DModel();
        
        if (selectedNodeId) {
            renderNodeDetails(selectedNodeId);
        } else {
            // Select Salon by default if available
            if (dashboardNodesData.find(n => n.id === 'Sensor:s1')) {
                selectNode('s1');
            }
        }
        updateLastUpdate();
    } catch (e) {
        console.error('Error fetching nodos:', e);
        document.getElementById('last-update').innerText = 'Error de conexión';
        document.querySelector('.dot').style.backgroundColor = 'var(--danger)';
    }
}

function selectNode(id) {
    selectedNodeId = `Sensor:${id}`;
    
    // Highlight room in 3D model
    document.querySelectorAll('.room').forEach(el => el.classList.remove('active'));
    const roomEl = document.getElementById(`room-${id}`);
    if (roomEl) roomEl.classList.add('active');
    if (typeof window.highlightRoom3D === 'function') {
        window.highlightRoom3D(id);
    }
    
    renderNodeDetails(selectedNodeId);
}

function update3DModel() {
    // We could add status indicators to the 3D model (e.g. red dot if disconnected)
    dashboardNodesData.forEach(n => {
        const shortId = n.id.replace('Sensor:', '');
        const dot = document.querySelector(`#room-${shortId} .node-dot`);
        if (dot) {
            dot.style.backgroundColor = n.temperature ? 'var(--success)' : 'var(--warning)';
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
            <div class="sensor-item"><span class="sensor-label">Vibración (Seguridad)</span><span class="sensor-value">${n.accelerationMagnitude || '--'} g</span></div>
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
                <span class="badge ${n.temperature ? 'good' : 'warn'}">${n.temperature ? 'En línea' : 'Sin conexión'}</span>
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
    try {
        await fetch(`${API_BASE}/nfc/uids`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({uid: uid})
        });
        document.getElementById('new-uid').value = '';
        fetchUIDs();
    } catch(e) {
        alert("Error al registrar la nueva tarjeta");
    }
}

async function deleteUID(uid) {
    if(!confirm(`¿Revocar acceso a la tarjeta con código ${uid}?`)) return;
    try {
        await fetch(`${API_BASE}/nfc/uids/${uid}`, { method: 'DELETE' });
        fetchUIDs();
    } catch(e) {
        alert("Error al revocar la tarjeta");
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
