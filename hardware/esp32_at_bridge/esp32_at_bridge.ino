/*
 * ESP32 AT Command Bridge for REYAX RYW122 UWB Module
 *
 * Purpose:
 *   Acts as a transparent serial bridge between your PC and the RYW122.
 *   You type AT commands in the Serial Monitor → ESP32 forwards them to
 *   the RYW122 → response is sent back to Serial Monitor.
 *
 * Wiring (RYUW122 <-> ESP32-WROOM-32):
 *   RYUW122 VCC  →  ESP32 3V3   (pin 2, right side)
 *   RYUW122 GND  →  ESP32 GND   (pin 4, right side)
 *   RYUW122 TXD  →  ESP32 GPIO16 / RX2  (pin 12, right side)
 *   RYUW122 RXD  →  ESP32 GPIO17 / TX2  (pin 14, right side)
 *   RYUW122 NRST →  ESP32 GPIO4  (pin 10, right side)
 *
 * How to use:
 *   1. Flash this sketch to your ESP32.
 *   2. Open Serial Monitor at 115200 baud, line ending = "Both NL & CR".
 *   3. Type AT commands (see at_commands_guide.md) and press Enter.
 *   4. The response from RYW122 will appear in the monitor.
 */

// ── Serial port settings ──────────────────────────────────────────────────────
#define PC_BAUD       115200   // USB Serial (PC <-> ESP32)
#define UWB_BAUD      115200   // Hardware Serial (ESP32 <-> RYW122); change if needed

// ── RYW122 UART pins on ESP32 ─────────────────────────────────────────────────
#define UWB_RX_PIN    16       // ESP32 GPIO16 receives data from RYW122 TX
#define UWB_TX_PIN    17       // ESP32 GPIO17 sends data to RYW122 RX

// ── Optional: hard-reset pin ──────────────────────────────────────────────────
// If your RYW122 RESET pin is wired to ESP32, set this. Otherwise leave -1.
#define UWB_RESET_PIN -1       // Optional: wire RYUW122 NRST → GPIO4 for software reset. -1 = not connected

// ── Timeout for collecting a full response ────────────────────────────────────
#define RESPONSE_TIMEOUT_MS 500

// ─────────────────────────────────────────────────────────────────────────────

HardwareSerial uwbSerial(2);   // UART2 of ESP32

// Forward declarations
void sendCommand(const String& cmd);
void readResponse();
void hardReset();

// ─────────────────────────────────────────────────────────────────────────────

void setup() {
  Serial.begin(PC_BAUD);
  while (!Serial) { delay(10); }

  uwbSerial.begin(UWB_BAUD, SERIAL_8N1, UWB_RX_PIN, UWB_TX_PIN);

  if (UWB_RESET_PIN >= 0) {
    pinMode(UWB_RESET_PIN, OUTPUT);
    digitalWrite(UWB_RESET_PIN, HIGH);
  }

  delay(500);   // Give RYW122 time to boot

  Serial.println("==============================================");
  Serial.println("  ESP32 <-> REYAX RYW122 AT Command Bridge  ");
  Serial.println("==============================================");
  Serial.println("Type an AT command and press Enter.");
  Serial.println("Line ending must be set to: Both NL & CR");
  Serial.println();
  Serial.println("Quick-start commands:");
  Serial.println("  AT             -> check connection");
  Serial.println("  AT+UID?        -> read module UID");
  Serial.println("  AT+MODE?       -> 0=Tag, 1=Anchor");
  Serial.println("  AT+TXPOWER?    -> TX power (0..33 dBm approx)");
  Serial.println("  AT+RANGINGMODE?-> check ranging mode");
  Serial.println("==============================================");
  Serial.println();

  // Auto-test connection on startup
  sendCommand("AT");
}

// ─────────────────────────────────────────────────────────────────────────────

void loop() {
  // ── PC → RYW122 ─────────────────────────────────────────────
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.length() == 0) return;

    // Built-in helper: type RESET to hard-reset via GPIO
    if (cmd.equalsIgnoreCase("RESET") && UWB_RESET_PIN >= 0) {
      hardReset();
      return;
    }

    // Echo command back so user can see what was sent
    Serial.print(">> Sent   : ");
    Serial.println(cmd);

    sendCommand(cmd);
    readResponse();
  }

  // ── RYW122 → PC (unsolicited messages, e.g. ranging results) ──
  while (uwbSerial.available()) {
    Serial.write(uwbSerial.read());
  }
}

// ─────────────────────────────────────────────────────────────────────────────

// Send a command to RYW122 (appends \r\n as required by AT protocol)
void sendCommand(const String& cmd) {
  uwbSerial.print(cmd);
  uwbSerial.print("\r\n");
}

// Collect and print the response until the line is idle for RESPONSE_TIMEOUT_MS
void readResponse() {
  String response = "";
  unsigned long start = millis();

  while (millis() - start < RESPONSE_TIMEOUT_MS) {
    while (uwbSerial.available()) {
      char c = (char)uwbSerial.read();
      response += c;
      start = millis();   // reset timeout on each incoming byte
    }
  }

  response.trim();
  if (response.length() > 0) {
    Serial.print("<< Response: ");
    Serial.println(response);
  } else {
    Serial.println("<< Response: (no response — check wiring or baud rate)");
  }
  Serial.println();
}

// Hard-reset the RYW122 via the RESET GPIO pin
void hardReset() {
  Serial.println(">> Hard-resetting RYW122...");
  digitalWrite(UWB_RESET_PIN, LOW);
  delay(100);
  digitalWrite(UWB_RESET_PIN, HIGH);
  delay(500);
  Serial.println("<< Reset done. Re-testing connection...");
  sendCommand("AT");
  readResponse();
}
