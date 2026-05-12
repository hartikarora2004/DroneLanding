# REYAX RYW122 — AT Commands Guide
# Goal: Diagnose and fix the 9m range limitation (rated 100m)

## How to Use
1. Flash `esp32_at_bridge/esp32_at_bridge.ino` to your ESP32.
2. Open Arduino Serial Monitor → **115200 baud** → **Both NL & CR** line ending.
3. Run commands in the order listed in each section below.

---

## STEP 1 — Verify Connection

```
AT
```
Expected: `OK`
If no response → check wiring, baud rate, VCC.

```
AT+UID?
```
Returns the unique hardware ID of the module.

---

## STEP 2 — Read Current Configuration

Run ALL of these first to know your baseline before changing anything.

```
AT+MODE?
```
- `0` = Tag (mobile node, measures distances)
- `1` = Anchor (fixed reference node)

```
AT+NETWORKID?
```
All modules in the same network must share the same Network ID.

```
AT+ADDRESS?
```
Each module must have a unique address.

```
AT+TXPOWER?
```
Transmit power level. Higher = longer range.
Note the current value before changing.

```
AT+RANGINGMODE?
```
Ranging mode affects accuracy vs. range trade-off.

```
AT+DATARATE?
```
Data rate. **Lower data rate = longer range and better sensitivity.**

```
AT+PREAMBLE?
```
Preamble length. **Longer preamble = better range but slower.**

```
AT+CHANNEL?
```
UWB channel (1–15). Different channels have different ranges.

---

## STEP 3 — Fix Range: Change Settings for Maximum Range

Run these commands to reconfigure for maximum range.
Always read the current value first (STEP 2) before writing.

### 3a. Set Maximum TX Power
```
AT+TXPOWER=33
```
Sets TX power to maximum (~33 dBm equivalent index).
Check datasheet for the valid max index for RYW122.

### 3b. Set Lowest Data Rate
```
AT+DATARATE=0
```
`0` = lowest data rate → best sensitivity → longest range.
Higher data rates (1, 2) trade range for speed.

### 3c. Set Longest Preamble
```
AT+PREAMBLE=12
```
Longer preamble (higher index) = better receiver sensitivity.
Typical values: 0 (short/fast) to 12 (long/long-range).

### 3d. Select Best Channel
```
AT+CHANNEL=5
```
Channel 5 (~6.5 GHz) generally offers the best range for RYW122.
Channels 1–4 are lower frequency; channel 5, 7, 9 are common choices.

### 3e. Apply Changes (Reset Module)
```
AT+RESET
```
Settings take effect after reset.

---

## STEP 4 — Verify New Configuration

After reset, re-read all settings to confirm they were saved:

```
AT+TXPOWER?
AT+DATARATE?
AT+PREAMBLE?
AT+CHANNEL?
```

---

## STEP 5 — Re-test Ranging

Set one module as Anchor and one as Tag, then check live ranging:

### On the Anchor module:
```
AT+MODE=1
AT+ADDRESS=1
AT+NETWORKID=1
AT+RESET
```

### On the Tag module:
```
AT+MODE=0
AT+ADDRESS=2
AT+NETWORKID=1
AT+RESET
```

Once both are running, the Tag will automatically start ranging.
You should see distance output in the Serial Monitor.

---

## STEP 6 — Common Causes of Short Range (Checklist)

| Issue                         | Fix                                      |
|-------------------------------|------------------------------------------|
| TX power too low              | `AT+TXPOWER=33` (or max valid value)    |
| Data rate too high            | `AT+DATARATE=0` (lowest)                |
| Short preamble                | `AT+PREAMBLE=12` (longest)             |
| Wrong channel                 | `AT+CHANNEL=5`                          |
| Network ID mismatch           | Must be same on all nodes               |
| Antenna blocked / obstructed  | Test in open space, no metal nearby     |
| Module in wrong mode          | Tag=0, Anchor=1                         |
| Low supply voltage            | Ensure stable 3.3V (not via GPIO pin)  |
| Baud rate mismatch            | Default is 115200 for RYW122            |

---

## Quick Reference — All Commands

| Command                  | Description                        |
|--------------------------|------------------------------------|
| `AT`                     | Connection test                    |
| `AT+UID?`                | Read module unique ID              |
| `AT+MODE=<0/1>`          | Set Tag(0) or Anchor(1) mode       |
| `AT+ADDRESS=<n>`         | Set module address                 |
| `AT+NETWORKID=<n>`       | Set network ID                     |
| `AT+TXPOWER=<n>`         | Set TX power                       |
| `AT+DATARATE=<n>`        | Set data rate (0=lowest/best range)|
| `AT+PREAMBLE=<n>`        | Set preamble length                |
| `AT+CHANNEL=<n>`         | Set UWB channel                    |
| `AT+RANGINGMODE=<n>`     | Set ranging mode                   |
| `AT+RESET`               | Reset module (apply changes)       |
