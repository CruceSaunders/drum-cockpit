// drum_reader.ino — read 8 drum pads, print events over USB serial
//
// Each pad is wired as a switch: one wire to a GPIO, common GND.
// When a pad is hit, the switch closes -> GPIO goes LOW.
//
// Wiring (GPIO -> pad number):
//   GPIO 5 = pad 1 (grey)       breadboard c1
//   GPIO 6 = pad 2 (red)        breadboard c2
//   GPIO 7 = pad 3 (purple)     breadboard c3
//   GPIO 4 = pad 4 (green)      breadboard h4
//   GPIO 3 = pad 5 (blue)       breadboard h5
//   GPIO 2 = pad 6 (tap-yellow) breadboard h6
//   GPIO 1 = pad 7 (brown)      breadboard h7
//   GPIO 0 = pad 8 (white)      breadboard h8
//   GND    = black              breadboard g2
//
// Onboard LED (GPIO 8) flashes briefly on every hit for visual feedback.

const int PAD_COUNT = 8;
const int PAD_PINS[PAD_COUNT]    = { 5, 6, 7, 4, 3, 2, 1, 0 };
const int PAD_NUMBERS[PAD_COUNT] = { 1, 2, 3, 4, 5, 6, 7, 8 };

const unsigned long DEBOUNCE_MS = 30;
const unsigned long LED_FLASH_MS = 30;
const int LED_PIN = 8;  // onboard LED, active LOW

int lastState[PAD_COUNT];
unsigned long lastChange[PAD_COUNT];

unsigned long ledOnUntil = 0;
bool ledOn = false;

void setup() {
  pinMode(LED_PIN, OUTPUT);

  // Boot signal: blink onboard LED 3 times so we can SEE the firmware started.
  for (int b = 0; b < 3; b++) {
    digitalWrite(LED_PIN, LOW);   // on
    delay(150);
    digitalWrite(LED_PIN, HIGH);  // off
    delay(150);
  }

  Serial.begin(115200);
  delay(500);  // let USB CDC enumerate
  Serial.println("drum_reader ready");

  for (int i = 0; i < PAD_COUNT; i++) {
    pinMode(PAD_PINS[i], INPUT_PULLUP);
    lastState[i] = HIGH;
    lastChange[i] = 0;
  }

  // After init, also print every second for the first 10 seconds so we can
  // tell whether serial is reaching the laptop even when no pads are hit.
  for (int s = 0; s < 5; s++) {
    Serial.print("heartbeat ");
    Serial.println(s);
    delay(1000);
  }
}

void flashLed() {
  digitalWrite(LED_PIN, LOW); // on
  ledOn = true;
  ledOnUntil = millis() + LED_FLASH_MS;
}

void loop() {
  unsigned long now = millis();

  // Manage LED flash without blocking
  if (ledOn && now >= ledOnUntil) {
    digitalWrite(LED_PIN, HIGH); // off
    ledOn = false;
  }

  for (int i = 0; i < PAD_COUNT; i++) {
    int state = digitalRead(PAD_PINS[i]);
    if (state != lastState[i] && (now - lastChange[i]) > DEBOUNCE_MS) {
      lastChange[i] = now;
      lastState[i] = state;
      if (state == LOW) {
        // pad pressed
        Serial.print("PAD ");
        Serial.println(PAD_NUMBERS[i]);
        flashLed();
      }
    }
  }
}
