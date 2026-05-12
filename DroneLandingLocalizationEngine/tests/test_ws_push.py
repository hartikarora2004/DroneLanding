"""
Manual test — pushes random position + distance data into the WebSocket
every second for 10 seconds. Open ui/index.html in a browser first.

Run:
    python -m DroneLandingLocalizationEngine.tests.test_ws_push
"""

import random
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from DroneLandingLocalizationEngine.websocket.server import WsServer

ANCHORS = {
    "Node1": [120,   0, 0],
    "Node2": [  0, 120, 0],
    "Node3": [120, 120, 0],
    "Node4": [  0,   0, 0],
}

def random_payload():
    x = random.uniform(-60, 180)
    y = random.uniform(-60, 240)
    z = random.uniform(0,   80)

    distances = {}
    for node, (ax, ay, az) in ANCHORS.items():
        d = ((x-ax)**2 + (y-ay)**2 + (z-az)**2) ** 0.5
        d += random.gauss(0, 3)          # add ±3 cm noise
        distances[node] = round(d, 2)

    return {
        "position":  [round(x, 2), round(y, 2), round(z, 2)],
        "distances": distances,
    }

if __name__ == "__main__":
    server = WsServer()
    server.start()

    print("Open ui/index.html in your browser, then watch the dot move.")
    print("Pushing data every 1 s for 10 s...\n")

    # Give the server a moment to bind
    time.sleep(0.5)

    DURATION = 60  # seconds
    for i in range(1, DURATION + 1):
        payload = random_payload()
        server.broadcast(payload)
        print(f"  [{i:>2}/{DURATION}] pos={payload['position']}  "
              f"Node1={payload['distances']['Node1']:.1f} cm")
        time.sleep(1)

    print("\nDone.")
