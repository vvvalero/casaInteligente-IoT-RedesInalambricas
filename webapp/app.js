const API_BASE = 'http://127.0.0.1:5000/api'; // Cambiar a http://api.vvalero.dev en prod

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
async function fetchNodos() {
    if (!document.getElementById('nodos-container')) return;
    try {
        const res = await fetch(`${API_BASE}/nodos`);
        const nodos = await res.json();
        renderNodos(nodos);
        updateLastUpdate();
    } catch (e) {
        console.error('Error fetching nodos:', e);
        document.getElementById('last-update').innerText = 'Error de conexión';
        document.querySelector('.dot').style.backgroundColor = 'var(--danger)';
    }
}

function renderNodos(nodos) {
    const container = document.getElementById('nodos-container');
    container.innerHTML = '';
    
    nodos.forEach(n => {
        const id = n.id.replace('Sensor:', '');
        const name = id === 's1' ? 'Salón' : id === 's2' ? 'Dormitorio' : 'Exterior';
        
        let extraHTML = '';
        if (id === 's1') {
            extraHTML = `
                <div class="sensor-item"><span class="sensor-label">Presión</span><span class="sensor-value">${n.barometricPressure || '--'} hPa</span></div>
                <div class="sensor-item"><span class="sensor-label">Humedad</span><span class="sensor-value">${n.humidity || '--'} %</span></div>
                <div class="sensor-item"><span class="sensor-label">Acelerómetro</span><span class="sensor-value">${n.accelerationMagnitude || '--'} g</span></div>
            `;
        } else if (id === 's2') {
            extraHTML = `
                <div class="sensor-item"><span class="sensor-label">Humedad</span><span class="sensor-value">${n.humidity || '--'} %</span></div>
                <div class="sensor-item"><span class="sensor-label">Último NFC</span><span class="sensor-value" style="font-size: 1rem; margin-top:4px;">${n.nfcDetected ? 'Detectado' : 'Esperando...'}</span></div>
            `;
        } else if (id === 's3') {
            extraHTML = `
                <div class="sensor-item"><span class="sensor-label">Presión</span><span class="sensor-value">${n.barometricPressure || '--'} hPa</span></div>
                <div class="sensor-item"><span class="sensor-label">Disp. BLE</span><span class="sensor-value">${n.bleDevicesNearby || '0'}</span></div>
            `;
        }

        const cardHTML = `
            <div class="card">
                <div class="card-header">
                    <div class="card-title">${name} (${id})</div>
                    <span class="badge ${n.temperature ? 'good' : 'warn'}">Conectado</span>
                </div>
                <div class="sensor-grid">
                    <div class="sensor-item">
                        <span class="sensor-label">Temperatura</span>
                        <span class="sensor-value">${n.temperature || '--'} °C</span>
                    </div>
                    <div class="sensor-item">
                        <span class="sensor-label">Luminosidad</span>
                        <span class="sensor-value">${n.luminosity || '--'} lx</span>
                    </div>
                    ${extraHTML}
                </div>
                <div style="border-top: 1px solid var(--border-color); padding-top: 1rem; margin-top: 0.5rem;">
                    <span class="sensor-label">Control LED RGB</span>
                    <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
                        <input type="color" id="color-${id}" value="#ff0000" style="width:100%; height:36px; padding:2px; cursor:pointer;">
                        <button class="btn-primary" onclick="sendColor('${id}')">Enviar</button>
                    </div>
                </div>
            </div>
        `;
        container.innerHTML += cardHTML;
    });
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
            body: JSON.stringify({r, g, b})
        });
        alert('Color enviado al ' + nodoId);
    } catch(e) {
        alert('Error al enviar color');
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
        document.getElementById('uid-list').innerHTML = 'Error al cargar UIDs';
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
        alert("Error añadiendo UID");
    }
}

async function deleteUID(uid) {
    if(!confirm(`¿Eliminar UID ${uid}?`)) return;
    try {
        await fetch(`${API_BASE}/nfc/uids/${uid}`, { method: 'DELETE' });
        fetchUIDs();
    } catch(e) {
        alert("Error eliminando UID");
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
    if (!document.getElementById('alertas-list')) return;
    try {
        const res = await fetch(`${API_BASE}/alertas`);
        const alertas = await res.json();
        const tbody = document.getElementById('alertas-list');
        tbody.innerHTML = '';
        if (alertas.length === 0) tbody.innerHTML = '<tr><td colspan="4">No hay alertas activas</td></tr>';
        
        alertas.forEach(al => {
            const date = formatDate(al.timestamp);
            const severity = al.severity === 'critical' ? 'bad' : al.severity === 'warning' ? 'warn' : 'good';
            tbody.innerHTML += `
                <tr>
                    <td>${date}</td>
                    <td>${al.refSensor || '--'}</td>
                    <td>${al.message || '--'}</td>
                    <td><span class="badge ${severity}">${al.severity || 'info'}</span></td>
                </tr>
            `;
        });
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
