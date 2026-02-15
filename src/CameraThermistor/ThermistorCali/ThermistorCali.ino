#include <Wire.h>
#include <Adafruit_BME280.h>

// --- 回路設定 ---
const float DIVIDE_RESISTOR = 47000.0; // 分圧抵抗 47kΩ
#define THERMISTOR_PIN_1 A0
#define THERMISTOR_PIN_2 A1

void setup() {
    Serial.begin(115200);
    Wire.begin();
    analogReadResolution(12); // ESP32-C3の12bit分解能
    Serial.println("--- Thermistor Calibration Mode ---");
    Serial.println("Soak thermistors in ice water and record the Resistance (Ohm).");
}

void loop() {
    long sumV1 = 0, sumV2 = 0;
    int samples = 20;

    // 精度を高めるため20回平均
    for(int i=0; i<samples; i++) {
        sumV1 += analogReadMilliVolts(THERMISTOR_PIN_1);
        sumV2 += analogReadMilliVolts(THERMISTOR_PIN_2);
        delay(10);
    }

    float avgV1 = (float)sumV1 / samples;
    float avgV2 = (float)sumV2 / samples;

    // 抵抗値 R = R_ref * (Vin / Vout - 1)
    float R1 = DIVIDE_RESISTOR * (3300.0 / avgV1 - 1.0);
    float R2 = DIVIDE_RESISTOR * (3300.0 / avgV2 - 1.0);

    Serial.print("Time: "); Serial.print(millis()/1000); Serial.print("s | ");
    Serial.print("R1 (A0): "); Serial.print(R1, 1); Serial.print(" Ohm | ");
    Serial.print("R2 (A1): "); Serial.print(R2, 1); Serial.println(" Ohm");

    delay(1000);
}