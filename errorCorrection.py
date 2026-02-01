import math
import statistics
import re

TRUE_DISTANCE = 45.0
INPUT_FILE = "uwb_raw_data.txt"

nodeToTest = "Node3"

analysis_map = []
valid = []

with open(INPUT_FILE) as f:
    for line in f:
        if ":" not in line:
            continue

        rhs = line.split(":", 1)[1]
        entries = [e.strip() for e in rhs.split("|")]

        # remove "(cm)" safely if present
        entries[-1] = re.sub(r"[^\d.\-]", "", entries[-1])

        map_current = {}

        for i in range(4):
            if entries[i] != "----" and entries[i] != "":
                map_current[f"Node{i+1}"] = float(entries[i])

        analysis_map.append(map_current)

# 🔍 extract values for the node under test
for entry in analysis_map:
    if nodeToTest in entry:
        valid.append(entry[nodeToTest])

if not valid:
    raise RuntimeError(f"No valid readings for {nodeToTest}")

# 📐 error calculations
errors = [abs(x - TRUE_DISTANCE) for x in valid]

rmse = math.sqrt(
    sum((x - TRUE_DISTANCE) ** 2 for x in valid) / len(valid)
)

print("\n📊 Results")
print(f"Node tested      : {nodeToTest}")
print(f"Valid readings   : {len(valid)}")
print(f"Mean error (cm)  : {statistics.mean(errors):.4f}")
print(f"RMSE (cm)        : {rmse:.4f}")
