// ============================================================
// ttn_cayenne_formatter.js — Payload Formatter TTN para Cayenne LPP
// ============================================================
// Pegar en: TTN Console → Applications → [tu-app] →
//           Payload formatters → Uplink → Custom Javascript formatter
//
// Decodifica automáticamente el formato Cayenne LPP multicampo.
// Los campos se identifican por su código de tipo — el orden
// en el payload no importa siempre que cada campo lleve su
// byte de canal y tipo.
//
// Tipos Cayenne LPP implementados:
//   0x67  Temperature       2 bytes signed  ÷10   → °C
//   0x68  Humidity          1 byte  unsigned ÷2   → %RH
//   0x73  Barometric Press. 2 bytes unsigned ÷10  → hPa
//   0x65  Luminosity        2 bytes unsigned       → lux
//   0x66  Presence          1 byte  0/1            → bool
//   0x00  Digital Input     1 byte  0/1            → bool
//   0x01  Digital Output    1 byte  0/1            → bool
//   0x02  Analog Input      2 bytes signed  ÷100  → float
// ============================================================

// Mapa de tipos: código → { tamaño en bytes del valor, función decodificadora }
var LPP_TYPES = {
  0x00: { size: 1, decode: function(b, i) { return b[i] ? 1 : 0; },            name: "digitalInput" },
  0x01: { size: 1, decode: function(b, i) { return b[i] ? 1 : 0; },            name: "digitalOutput" },
  0x02: { size: 2, decode: function(b, i) { return int16(b,i) / 100.0; },      name: "analogInput" },
  0x65: { size: 2, decode: function(b, i) { return uint16(b,i); },             name: "luminosity" },
  0x66: { size: 1, decode: function(b, i) { return b[i] === 1; },              name: "presence" },
  0x67: { size: 2, decode: function(b, i) { return int16(b,i) / 10.0; },       name: "temperature" },
  0x68: { size: 1, decode: function(b, i) { return b[i] / 2.0; },              name: "humidity" },
  0x73: { size: 2, decode: function(b, i) { return uint16(b,i) / 10.0; },      name: "barometricPressure" }
};

// ---- Funciones auxiliares de lectura de enteros ----

function uint16(bytes, offset) {
  return (bytes[offset] << 8) | bytes[offset + 1];
}

function int16(bytes, offset) {
  var val = uint16(bytes, offset);
  return val >= 0x8000 ? val - 0x10000 : val;
}

// ---- Decodificador principal uplink ----

function decodeUplink(input) {
  var bytes  = input.bytes;
  var result = {};
  var warnings = [];
  var i = 0;

  while (i < bytes.length) {
    // Leer canal (1 byte) y tipo (1 byte)
    if (i + 1 >= bytes.length) {
      warnings.push("Payload truncado en byte " + i);
      break;
    }

    var channel = bytes[i];
    var typeId  = bytes[i + 1];
    i += 2;

    var typeDef = LPP_TYPES[typeId];
    if (!typeDef) {
      warnings.push("Tipo desconocido 0x" + typeId.toString(16) + " en canal " + channel);
      break;
    }

    if (i + typeDef.size > bytes.length) {
      warnings.push("Payload demasiado corto para tipo 0x" + typeId.toString(16));
      break;
    }

    // Decodificar valor
    var valor = typeDef.decode(bytes, i);
    i += typeDef.size;

    // Construir clave: "nombreCampo_canal" (ej: temperature_1)
    var clave = typeDef.name + "_" + channel;
    result[clave] = valor;

    // También guardar con nombre sin canal para acceso directo
    // (si solo hay un sensor de cada tipo)
    if (result[typeDef.name] === undefined) {
      result[typeDef.name] = valor;
    }
  }

  // Validaciones de rango
  if (result.temperature !== undefined &&
      (result.temperature < -40 || result.temperature > 85)) {
    warnings.push("Temperatura fuera de rango: " + result.temperature + "°C");
  }
  if (result.humidity !== undefined &&
      (result.humidity < 0 || result.humidity > 100)) {
    warnings.push("Humedad fuera de rango: " + result.humidity + "%");
  }
  if (result.barometricPressure !== undefined &&
      (result.barometricPressure < 300 || result.barometricPressure > 1100)) {
    warnings.push("Presión fuera de rango: " + result.barometricPressure + " hPa");
  }

  // Añadir metadatos útiles para integraciones
  result.raw_hex = Array.from(bytes)
    .map(function(b) { return ("0" + b.toString(16)).slice(-2).toUpperCase(); })
    .join(" ");

  if (warnings.length > 0) {
    return { data: result, warnings: warnings };
  }
  return { data: result };
}

// ---- Codificador downlink ----
// Envía comandos a los actuadores del ESP32
//
// Ejemplos de uso desde TTN Console o API:
//   { "comando": "luz",    "valor": 1 }  → encender luz
//   { "comando": "ac",     "valor": 0 }  → apagar AC
//   { "comando": "alarma", "valor": 1 }  → activar alarma
//
// Formato: 2 bytes [cmd_id, valor]

var DOWNLINK_CMDS = {
  "luz":    0x01,
  "ac":     0x02,
  "alarma": 0x03
};

function encodeDownlink(input) {
  var data = input.data || {};

  if (!data.comando) {
    return { errors: ["Falta el campo 'comando'. Válidos: luz, ac, alarma"] };
  }

  var cmdId = DOWNLINK_CMDS[data.comando];
  if (cmdId === undefined) {
    return { errors: ["Comando desconocido: '" + data.comando +
                      "'. Válidos: " + Object.keys(DOWNLINK_CMDS).join(", ")] };
  }

  if (data.valor === undefined) {
    return { errors: ["Falta el campo 'valor' (0 = OFF, 1 = ON)"] };
  }

  var valor = parseInt(data.valor, 10);
  if (isNaN(valor)) {
    return { errors: ["El campo 'valor' debe ser 0 o 1"] };
  }
  valor = valor ? 1 : 0;

  return {
    bytes: [cmdId, valor],
    fPort: 1
  };
}


// ============================================================
// TESTS — pegar en la pestaña "Test" de TTN Payload Formatters
// ============================================================
//
// Test 1 — Lectura completa BME280 (5 campos, 13 bytes):
//   Canal 1 Temperatura 23.1°C:  01 67 00 E7
//   Canal 2 Humedad 55.0%:       02 68 6E
//   Canal 3 Presión 1013.2hPa:   03 73 27 94
//   Canal 4 Luminosidad 350lux:  04 65 01 5E
//   Canal 5 Presencia ON:        05 66 01
//   Hex completo: 01 67 00 E7 02 68 6E 03 73 27 94 04 65 01 5E 05 66 01
//
//   Resultado esperado:
//   {
//     "temperature_1": 23.1,  "temperature": 23.1,
//     "humidity_2":    55.0,  "humidity": 55.0,
//     "barometricPressure_3": 1013.2, "barometricPressure": 1013.2,
//     "luminosity_4":  350,   "luminosity": 350,
//     "presence_5":    true,  "presence": true
//   }
//
// Test 2 — Solo temperatura negativa (-4.5°C):
//   01 67 FF D3
//   Resultado: { "temperature_1": -4.5, "temperature": -4.5 }
//
// Test 3 — Downlink encender luz:
//   Input:  { "comando": "luz", "valor": 1 }
//   Output: bytes [0x01, 0x01], fPort 1
//
// Test 4 — Downlink apagar alarma:
//   Input:  { "comando": "alarma", "valor": 0 }
//   Output: bytes [0x03, 0x00], fPort 1
