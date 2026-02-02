"""
Docstring for DroneLandingLocalizationEngine.settings.settings
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional


class Settings:
    def __init__(self, env_path: Optional[Path | str] = None) -> None:
        # Default to DroneLandingLocalizationEngine/.env relative to this file.
        default_path = Path(__file__).resolve().parents[1] / ".env"
        self.env_path: Path = Path(env_path) if env_path else default_path
        self._values: Dict[str, str] = {}
        # print(self._values)
        self._load()

    def _load(self) -> None:
        if not self.env_path.exists():
            raise FileNotFoundError(f".env file not found at {self.env_path}")

        for raw_line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            if "=" not in line:
                continue  # Skip malformed lines quietly.

            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if not key:
                continue

            self._values[key] = value
            # Make values accessible as attributes (e.g., settings.COMPORT).
            setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)
    
    def getAttributes(self, key) -> Any:
        attributeMap = {}
        for i in key:
            attributeMap[i] = self._values.get(i)
        
        return attributeMap
    
    def printAttributes(self) -> Any:
        print("******************")
        for i in self._values:
            print(f"{i} \t \t \t : {self._values[i]}")
        print("******************")


# Singleton-style instance if callers want a ready-to-use settings object.
settings = Settings()


