import re

def parse_anchor_locations(line : str, missing_value = None) -> dict[str, float]:
    try:
        left, right = line.split(":")
        nodes = [n.strip() for n in left.split("|")]
        raw_vals = [v.strip() for v in right.split("|")]

        if len(nodes) != len(raw_vals):
            print(f"Values are invalid or incorrect:-) : {line}")
            return 

        values = []
        for v in raw_vals:
            if v == "----":
                values.append(missing_value)
            else:
                # Remove units like "(cm)", "cm", spaces, etc.
                cleaned = re.sub(r"[^\d.\-+eE]", "", v)
                values.append(float(cleaned))

        return dict(zip(nodes, values))

    except Exception as e:
        print(f"Invalid string value : {line}")