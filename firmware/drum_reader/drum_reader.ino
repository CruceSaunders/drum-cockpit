// drum_reader.ino — read drum pads, print events over USB serial.
//
// Each pad is wired as a switch: one wire to a GPIO, common GND.
// When a pad is hit, the switch closes -> GPIO goes LOW.
//
// PAD_NUMBERS uses the PHYSICAL drum layout (1-6, with 4 dead).
// See HARDWARE.md for the authoritative map.
//
// Wiring (GPIO -> physical pad #):
//   GPIO 5 = physical pad 1   wire Grey         breadboard c1
//   GPIO 7 = physical pad 2   wire Purple       breadboard c3
//   GPIO 6 = physical pad 3   wire Red          breadboard c2
//   GPIO 4 = (unmapped, dead) wire Green        breadboard h4  -> prints "PAD 99"
//   GPIO 3 = physical pad 4   wire Blue         breadboard h5
//   GPIO 2 = physical pad 5   wire Tap-Yellow   breadboard h6
//   GPIO 1 = physical pad 6   wire Brown        breadboard h7
//   GPIO 0 = physical pad 6   wire White        breadboard h8  (coupled w/ GPIO 1)
//   GND    = black                              breadboard g2
//
// The coupled pair (GPIO 1 + 0) both print PAD 6; the Python side debounces
// the duplicate event so taps register only once.
//
// Onboard LED (GPIO 8) flashes briefly on every hit for visual feedback.

const int PAD_COUNT = 8;
const int PAD_PINS[PAD_COUNT]    = {  5,  6,  7,  4,  3,  2,  1,  0 };
const int PAD_NUMBERS[PAD_COUNT] = {  1,  3,  2, 99,  4,  5,  6,  6 };

const unsigned long DEBOUNCE_MS = 30;
const unsigned long LED_FLASH_MS = 30;
const int LED_PIN = 8;  // onboard LED, active LOW

// Cross-pin debounce: when two different GPIOs map to the same physical pad
// number (coupled hardware pair: GPIOs 0+1 both fire PAD 6), only emit the
// first event. The second is suppressed inside the firmware, before reaching
// the Python side, so it can't slip past any host-side debounce timing.
const unsigned long CROSS_PIN_DEBOUNCE_MS = 120;
const int MAX_PAD_NUM = 6;
unsigned long lastPadEmitMs[MAX_PAD_NUM + 1] = {0};  // index by physical pad number 1..6

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
        int padNum = PAD_NUMBERS[i];

        // Cross-pin debounce for coupled pads (multiple GPIOs → same pad #).
        // Suppress events that arrive within CROSS_PIN_DEBOUNCE_MS of the
        // previous emission for the same padNum.
        if (padNum >= 1 && padNum <= MAX_PAD_NUM) {
          if (now - lastPadEmitMs[padNum] < CROSS_PIN_DEBOUNCE_MS) {
            continue;  // suppressed duplicate (from coupled pair)
          }
          lastPadEmitMs[padNum] = now;
        }

        Serial.print("PAD ");
        Serial.println(padNum);
        flashLed();
      }
    }
  }
}
