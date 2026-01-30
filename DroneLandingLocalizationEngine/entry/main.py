"""
This is the entry point of the code.
"""

from DroneLandingLocalizationEngine.settings import settings

if __name__ == "__main__":
    print(settings.getAttributes(['NAME', 'COMPORT']))

