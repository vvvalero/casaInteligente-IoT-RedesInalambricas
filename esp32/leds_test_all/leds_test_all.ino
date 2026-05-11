#include <Arduino.h>

struct IndicatorPins {
  uint8_t redPin;
  uint8_t greenPin;
  const char* name;
};

const IndicatorPins indicators[] = {
  {25, 26, "Indicador 1 - Nodo s1 (Salon)"},
  {12, 13, "Indicador 2 - Nodo s2 (Dormitorio)"},
  {15, 2,  "Indicador 3 - Nodo s3 (Exterior)"},
  {5, 18,  "Indicador 4 - Temperatura"},
  {19, 23, "Indicador 5 - Presion"},
  {4, 16,  "Indicador 6 - Humedad"},
  {17, 27, "Indicador 7 - Sistema"},
  {33, 14, "Indicador 8 - Acceso NFC"}
};

const size_t indicatorCount = sizeof(indicators) / sizeof(indicators[0]);

static void setAllLow() {
  for (size_t i = 0; i < indicatorCount; ++i) {
    digitalWrite(indicators[i].redPin, LOW);
    digitalWrite(indicators[i].greenPin, LOW);
  }
}

static void showIndicator(size_t index, bool redOn, bool greenOn) {
  setAllLow();
  digitalWrite(indicators[index].redPin, redOn ? HIGH : LOW);
  digitalWrite(indicators[index].greenPin, greenOn ? HIGH : LOW);

  Serial.print("[TEST] ");
  Serial.print(indicators[index].name);
  Serial.print(" -> R=");
  Serial.print(redOn ? "ON" : "OFF");
  Serial.print(", G=");
  Serial.println(greenOn ? "ON" : "OFF");
}

static void allOn() {
  for (size_t i = 0; i < indicatorCount; ++i) {
    digitalWrite(indicators[i].redPin, HIGH);
    digitalWrite(indicators[i].greenPin, HIGH);
  }
}

void setup() {
  Serial.begin(115200);
  delay(1000);

  for (size_t i = 0; i < indicatorCount; ++i) {
    pinMode(indicators[i].redPin, OUTPUT);
    pinMode(indicators[i].greenPin, OUTPUT);
  }

  setAllLow();
  Serial.println();
  Serial.println("=== TEST DE LEDS ESP32 ===");
  Serial.println("Cada indicador se encendera en rojo, verde y ambos.");
}

void loop() {
  for (size_t i = 0; i < indicatorCount; ++i) {
    showIndicator(i, true, false);
    delay(700);
    showIndicator(i, false, true);
    delay(700);
    showIndicator(i, true, true);
    delay(700);
    setAllLow();
    delay(250);
  }

  Serial.println("[TEST] Todos los LEDs encendidos");
  allOn();
  delay(2000);

  Serial.println("[TEST] Todos los LEDs apagados");
  setAllLow();
  delay(1000);
}