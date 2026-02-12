#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// --- APモード設定 ---
const char* ap_ssid = "XIAO-C3-Sensor"; // WiFiの名前
const char* ap_pass = "12345678";        // パスワード（8文字以上）
const char* pc_ip   = "192.168.4.2";    // APモードで最初に接続したPCに割り振られるIP
const int udp_port  = 5005;

WiFiUDP udp;
Adafruit_BME280 bme;

#define THERMISTOR_PIN_1 A0
#define THERMISTOR_PIN_2 A1
#define DIVIDE_RESISTOR  47000.0
#define B_COEFFICIENT    3435.0
#define NOMINAL_RESIST   10000.0
#define NOMINAL_TEMP     25.0

unsigned long lastSampleTime = 0;
int sampleCount = 0;
long sumV1 = 0, sumV2 = 0;

float convertToTemp(float v_out_mv) {
    float v_in_mv = 3300.0;
    if (v_out_mv <= 0 || v_out_mv >= v_in_mv) return -999.0;
    float res = DIVIDE_RESISTOR * (v_in_mv / v_out_mv - 1.0);
    float steer = log(res / NOMINAL_RESIST) / B_COEFFICIENT;
    steer += 1.0 / (NOMINAL_TEMP + 273.15);
    return (1.0 / steer) - 273.15;
}

void setup() {
    Serial.begin(115200);
    Wire.begin();
    if (!bme.begin(0x76)) { while(1); }
    analogReadResolution(12);

    // APモードの開始
    Serial.print("Setting up Access Point...");
    WiFi.softAP(ap_ssid, ap_pass);
    Serial.println("Done.");
    Serial.print("AP IP address: ");
    Serial.println(WiFi.softAPIP()); // 通常 192.168.4.1
}

void loop() {
    unsigned long currentMillis = millis();
    if (currentMillis - lastSampleTime >= 100) {
        lastSampleTime = currentMillis;
        sumV1 += analogReadMilliVolts(THERMISTOR_PIN_1);
        sumV2 += analogReadMilliVolts(THERMISTOR_PIN_2);
        sampleCount++;

        if (sampleCount >= 10) {
            float t1 = convertToTemp(sumV1 / 10.0);
            float t2 = convertToTemp(sumV2 / 10.0);
            
            String msg = String(bme.readTemperature(), 1) + "," + 
                         String(bme.readHumidity(), 1) + "," + 
                         String(bme.readPressure()/100.0F, 1) + "," + 
                         String(t1, 1) + "," + String(t2, 1);

            udp.beginPacket(pc_ip, udp_port);
            udp.print(msg);
            udp.endPacket();

            Serial.println("Sent to AP-Client: " + msg);
            sampleCount = 0; sumV1 = 0; sumV2 = 0;
        }
    }
}