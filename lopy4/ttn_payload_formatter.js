// ttn_payload_formatter.js — Casa Inteligente IoT · 3x LoPy4 + Pysense

var LPP_TYPES = {
  0x00: { size:1, name:'digitalInput',      decode:function(b,i){ return b[i]; } },
  0x02: { size:2, name:'analogInput',       decode:function(b,i){ return int16(b,i)/100.0; } },
  0x65: { size:2, name:'luminosity',        decode:function(b,i){ return uint16(b,i); } },
  0x67: { size:2, name:'temperature',       decode:function(b,i){ return int16(b,i)/10.0; } },
  0x68: { size:1, name:'humidity',          decode:function(b,i){ return b[i]/2.0; } },
  0x71: { size:6, name:'accelerometer',     decode:function(b,i){ return {x:int16(b,i)/1000.0, y:int16(b,i+2)/1000.0, z:int16(b,i+4)/1000.0}; } },
  0x73: { size:2, name:'barometricPressure',decode:function(b,i){ return uint16(b,i)/10.0; } }
};

var ROOMS = { 1:'salon', 2:'dormitorio', 3:'exterior' };

function uint16(b,i){ return (b[i]<<8)|b[i+1]; }
function int16(b,i){ var v=uint16(b,i); return v>=0x8000?v-0x10000:v; }

function decodeUplink(input) {
  var bytes=input.bytes, result={}, warnings=[], i=0;
  while(i<bytes.length){
    if(i+1>=bytes.length){ warnings.push('Payload truncado'); break; }
    var ch=bytes[i], tid=bytes[i+1]; i+=2;
    var td=LPP_TYPES[tid];
    if(!td){ warnings.push('Tipo desconocido: 0x'+tid.toString(16)); break; }
    if(i+td.size>bytes.length){ warnings.push('Payload corto'); break; }
    var val=td.decode(bytes,i); i+=td.size;
    result[td.name+'_'+ch]=val;
    if(result[td.name]===undefined) result[td.name]=val;
  }

  // Habitación
  var roomId = result.digitalInput_6 || result.digitalInput_5;
  if(roomId!==undefined){ result.room=ROOMS[roomId]||'desconocida'; result.roomId=roomId; }

  // NFC (nodo dormitorio)
  if(result.analogInput_4!==undefined){
    result.nfcDetected = result.analogInput_4 > 0;
    result.nfcUidPartial = Math.round(result.analogInput_4*100);
  }

  // BLE aforo (nodo exterior)
  if(result.digitalInput_4!==undefined && result.room==='exterior'){
    result.bleDevicesNearby = result.digitalInput_4;
    result.aforoAlerta = result.bleDevicesNearby > 5;
  }

  // Magnitud acelerómetro (nodo salon)
  if(result.accelerometer){
    var a=result.accelerometer;
    result.accelerationMagnitude = Math.sqrt(a.x*a.x+a.y*a.y+a.z*a.z);
    result.vibrationDetected = result.accelerationMagnitude > 1.5;
  }

  result.raw_hex = Array.from(bytes).map(function(b){ return ('0'+b.toString(16)).slice(-2).toUpperCase(); }).join(' ');
  return warnings.length>0 ? {data:result,warnings:warnings} : {data:result};
}

function encodeDownlink(input) {
  var data=input.data||{}, cmd=data.cmd;
  if(!cmd) return {errors:["Falta 'cmd'"]};
  if(cmd==='led_color'||cmd==='led_parpadeo'){
    var tipo=cmd==='led_color'?0x01:0x02;
    return {bytes:[tipo, data.r||0, data.g||0, data.b||0], fPort:1};
  }
  var MAP={'nfc_ok':[0x03],'nfc_denied':[0x04],'aforo_alerta':[0x05],
           'temp_frio':[0x06,0x00],'temp_calor':[0x06,0x01],'exterior_alerta':[0x07]};
  if(MAP[cmd]) return {bytes:MAP[cmd], fPort:1};
  return {errors:['Comando desconocido: '+cmd]};
}
