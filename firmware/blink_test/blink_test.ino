// blink_test.ino
// Simple test: blink the onboard LED once every 2 seconds.
// Confirms the ESP32-C3 is responsive and we can upload code to it.
//
// ESP32-C3 SuperMini: onboard LED is on GPIO 8, active-LOW
// (LOW = LED on, HIGH = LED off).

#define LED_PIN 8

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(115200);
  delay(200);
  Serial.println("blink_test running — should blink once every 2 seconds.");
}

void loop() {
  digitalWrite(LED_PIN, LOW);   // LED ON
  delay(1000);
  digitalWrite(LED_PIN, HIGH);  // LED OFF
  delay(1000);
}
