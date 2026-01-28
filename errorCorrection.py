#Start : Input format :-> Average Anchor error:
#A1  | A2 | A3  | A4 ... | ... | ... | ...

import math
import statistics

TRUE_DISTANCE = 1.0
INPUT_FILE = "uwb_raw_data.txt"

valid = []
total = 0
invalid = 0

with open(INPUT_FILE) as f:
    for line in f:
        total += 1
        value = line.strip()

        if value == "...":
            invalid += 1
            continue

        try:
            valid.append(float(value))
        except ValueError:
            invalid += 1

if not valid:
    raise RuntimeError("No valid readings")

# Let:
# - d̂ = measured distance (i-th reading)
# - d = true (ground-truth) distance
# - e = measured signed errors
# error:
# ei = d^i - d

# Absolute error:
# |ei| = |di - d|

errors = [abs(x - TRUE_DISTANCE) for x in valid]
#Root Mean Square Error
rmse = math.sqrt(sum((x - TRUE_DISTANCE) ** 2 for x in valid) / len(valid))

print("\n📊 Results")
print(f"Total pings      : {total}")
print(f"Valid pings      : {len(valid)}")
print(f"Invalid pings    : {invalid}")
print(f"Packet loss (%)  : {invalid / total * 100:.2f}")
print(f"Mean error (m)   : {statistics.mean(errors):.4f}")
print(f"RMSE (m)         : {rmse:.4f}")
