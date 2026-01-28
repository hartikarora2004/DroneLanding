import serial

PORT = "COM5"
BAUDRATE = 115200
OUTPUT_FILE = "uwb_raw_data.txt"

ser = serial.Serial(PORT, BAUDRATE, timeout=1)

print("📡 Logging UWB data, CTRL+C to stop")

with open(OUTPUT_FILE, "a") as f:
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue

            f.write(line + "\n")
            f.flush()
            print(line)

    except KeyboardInterrupt:
        print("\n Logging stopped")

    finally:
        ser.close()
