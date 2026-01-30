import re

from DroneLandingLocalizationEngine.serial.serialization import UwbReading
from typing import Dict, Optional


def parse_line(line: str) -> UwbReading:
        """
        Parse a pipe-separated line into numeric values.

        Accepts tokens like ``A1=1.23``, ``A2: 4.56``, ``A3 7.89``.
        Missing tokens represented by ``...`` or empty fields become ``None``.
        """
        tokens = [tok.strip() for tok in line.split("|")]
        values: Dict[str, Optional[float]] = {}
        pattern = re.compile(r"(?P<label>[A-Za-z0-9]+)\\s*[:=]?\\s*(?P<val>[-+]?[0-9]*\\.?[0-9]+)?")

        for tok in tokens:
            if tok in ("", "..."):
                continue

            match = pattern.fullmatch(tok)
            if not match:
                # Unknown token, keep raw string as None-mapped
                values[tok] = None
                continue

            label = match.group("label")
            val_str = match.group("val")
            values[label] = float(val_str) if val_str else None

        return UwbReading(values=values, raw=line)
