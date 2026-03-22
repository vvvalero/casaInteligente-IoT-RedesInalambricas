// ============================================================
// ttn_cayenne_formatter.js — Payload Formatter TTN
// Casa Inteligente IoT · LoPy4 + Pysense
// ============================================================
// Pegar en: TTN Console → Applications → [tu-app] →
//           Payload formatters → Uplink → Custom Javascript
//
// Campos enviados por el LoPy4:
//   Canal 1 → Temperatura    (tipo 0x67, 2 bytes, ÷10 °C)
//   Canal 2 → Humedad        (tipo 0x68, 1 byte,  ÷2  %RH)
//   Canal 3 → Luminosidad    (tipo 0x65, 2 bytes, lux)
//   Canal 4 → Habitación     (tipo 0x00, 1 byte,  1-5)
// ============================================================

var LPP_TYPES = {
  0x00: { size: 1, decode: function(b,i){ return b[i]; },                      name: 'digitalInput' },
  0x01: { size: 1, decode: function(b,i){ return b[i]; },                      name: 'digitalOutput' },
  0x65: { size: 2, decode: function(b,i){ return uint16(b,i); },               name: 'luminosity' },
  0x66: { size: 1, decode: function(b,i){ return b[i] === 1; },                name: 'presence' },
  0x67: { size: 2, decode: function(b,i){ return int16(b,i) / 10.0; },         name: 'temperature' },
  0x68: { size: 1, decode: function(b,i){ return b[i] / 2.0; },               name: 'humidity' },
  0x73: { size: 2, decode: function(b,i){ return uint16(b,i) / 10.0; },        name: 'barometricPressure' }
};

var HABITACIONES = { 1:'salon', 2:'cocina', 3:'dormitorio', 4:'bano', 5:'exterior' };

function uint16(b, i) { return (b[i] << 8) | b[i+1]; }
function int16(b, i)  { var v = uint16(b,i); return v >= 0x8000 ? v - 0x10000 : v; }

function decodeUplink(input) {
  var bytes = input.bytes;
  var result = {};
  var warnings = [];
  var i = 0;

  while (i < bytes.length) {
    if (i + 1 >= bytes.length) { warnings.push('Payload truncado'); break; }
    var channel = bytes[i];
    var typeId  = bytes[i+1];
    i += 2;

    var td = LPP_TYPES[typeId];
    if (!td) { warnings.push('Tipo desconocido: 0x' + typeId.toString(16)); break; }
    if (i + td.size > bytes.length) { warnings.push('Payload corto'); break; }

    var valor = td.decode(bytes, i);
    i += td.size;

    result[td.name + '_' + channel] = valor;
    if (result[td.name] === undefined) result[td.name] = valor;
  }

  // Traducir habitación a nombre legible
  if (result.digitalInput_4 !== undefined) {
    result.room = HABITACIONES[result.digitalInput_4] || 'desconocida';
  }

  result.raw_hex = Array.from(bytes)
    .map(function(b){ return ('0'+b.toString(16)).slice(-2).toUpperCase(); })
    .join(' ');

  return warnings.length > 0 ? { data: result, warnings: warnings } : { data: result };
}

function encodeDownlink(input) {
  var CMDS = { 'luz': 0x01, 'ac': 0x02, 'alarma': 0x03 };
  var data = input.data || {};
  if (!data.comando) return { errors: ["Falta 'comando': luz, ac, alarma"] };
  var cmdId = CMDS[data.comando];
  if (cmdId === undefined) return { errors: ['Comando desconocido: ' + data.comando] };
  if (data.valor === undefined) return { errors: ["Falta 'valor' (0 o 1)"] };
  return { bytes: [cmdId, data.valor ? 1 : 0], fPort: 1 };
}

// ============================================================
// TEST — pegar en la pestaña Test de TTN:
// Hex: 01 67 00 E7 02 68 6E 03 65 01 5E 04 00 01
//
// Resultado esperado:
// {
//   "temperature": 23.1,
//   "humidity": 55.0,
//   "luminosity": 350,
//   "digitalInput_4": 1,
//   "room": "salon"
// }
// ============================================================
