#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>

// ==========================================
// 1. 個別調整パラメータ（氷水試験後にここを書き換える）
// ==========================================
// 氷水(0℃)の時にシリアルモニタに表示された抵抗値(Ohm)を入力してください
float R0_TH1 = 27600.0; // サーミスタ1(A0)の0℃抵抗値。実測値を入れる
float R0_TH2 = 27920.0; // サーミスタ2(A1)の0℃抵抗値。実測値を入れる
const float T0 = 0.0;   // 基準温度(氷水なので0℃固定)
const float B  = 2939.0; // サーミスタのB定数

// ==========================================
// 2. システム・通信設定
// ==========================================
const char* ap_ssid = "XIAO-C3-FreezerTest";
const char* ap_pass = "12345678";
const char* pc_ip   = "192.168.4.2";
const int udp_port  = 5005;
const float R_DIV   = 47100.0; // 分圧抵抗 47kΩ

WiFiUDP udp;
Adafruit_BME280 bme;

#define PIN_TH1 A0
#define PIN_TH2 A1

unsigned long lastSampleTime = 0;
int sampleCount = 0;
long sumV1 = 0, sumV2 = 0;

// 温度計算関数（Steinhart-Hartの簡略式）
float calculateTemp(float v_mv, float r0, float t0, float b) {
    if (v_mv <= 0 || v_mv >= 3300.0) return -999.0;
    // 現在のサーミスタ抵抗値を算出
    float r = R_DIV * (3300.0 / v_mv - 1.0);
    // 温度計算
    float steer = log(r / r0) / b;
    steer += 1.0 / (t0 + 273.15);
    return (1.0 / steer) - 273.15;
}

// 抵抗値計算関数（キャリブレーションの数値確認用）
float getResistance(float v_mv) {
    if (v_mv <= 0 || v_mv >= 3300.0) return 0;
    return R_DIV * (3300.0 / v_mv - 1.0);
}

void setup() {
    Serial.begin(115200);
    Wire.begin();
    
    // BME280の初期化
    if (!bme.begin(0x76)) {
        Serial.println("Could not find a valid BME280 sensor!");
    }
    
    analogReadResolution(12); // ESP32-C3の12bit分解能を設定

    // APモード（親機モード）の開始
    WiFi.softAP(ap_ssid, ap_pass);
    
    Serial.println("\n--- XIAO C3 Test System Started ---");
    Serial.print("AP SSID: "); Serial.println(ap_ssid);
    Serial.print("AP IP: "); Serial.println(WiFi.softAPIP());
    Serial.println("------------------------------------");
}

void loop() {
    unsigned long currentMillis = millis();

    // 100msごとにサンプリング (10Hz)
    if (currentMillis - lastSampleTime >= 100) {
        lastSampleTime = currentMillis;
        sumV1 += analogReadMilliVolts(PIN_TH1);
        sumV2 += analogReadMilliVolts(PIN_TH2);
        sampleCount++;

        // 10回（1秒）たまったら計算して送信
        if (sampleCount >= 10) {
            float avgV1 = (float)sumV1 / 10.0;
            float avgV2 = (float)sumV2 / 10.0;

            // 1. キャリブレーション用：現在の抵抗値をシリアル出力（氷水調整用）
            float res1 = getResistance(avgV1);
            float res2 = getResistance(avgV2);
            Serial.print("[CALIB] R1: "); Serial.print(res1, 1);
            Serial.print(" Ohm, R2: "); Serial.print(res2, 1); Serial.println(" Ohm");

            // 2. 本番用：キャリブレーション値を反映した高精度温度
            float t1 = calculateTemp(avgV1, R0_TH1, T0, B);
            float t2 = calculateTemp(avgV2, R0_TH2, T0, B);
            float bt = bme.readTemperature();
            float bh = bme.readHumidity();
            float bp = bme.readPressure() / 100.0F;

            // 3. UDP送信 (PCのダッシュボード用)
            // 形式: BME温度, 湿度, 気圧, サーミスタ1, サーミスタ2
            String msg = String(bt, 1) + "," + String(bh, 1) + "," + String(bp, 1) + "," + 
                         String(t1, 1) + "," + String(t2, 1);

            udp.beginPacket(pc_ip, udp_port);
            udp.print(msg);
            udp.endPacket();

            // リセット
            sampleCount = 0;
            sumV1 = 0;
            sumV2 = 0;
        }
    }
}