"""Start live ESP32 CSI capture via UDP → Dashboard pipeline."""
import websocket
import json
import time
import sys

ws = websocket.create_connection("ws://localhost:5000/ws", timeout=5)
print("Connected to dashboard WebSocket")

ws.send(json.dumps({"type": "startProcessing", "data": {"customName": "Live ESP32 CSI Capture"}}))
print("Processing started!")
print("ESP32 UDP data on port 5005 -> Dashboard visualization")
print("Open http://localhost:5000 to see the live visualization")
print("Press Ctrl+C to stop...")

try:
    while True:
        try:
            ws.settimeout(3)
            msg = ws.recv()
            data = json.loads(msg)
            if data.get("type") == "status":
                s = data["data"]
                samples = s.get("samplesReceived", 0)
                frames = s.get("framesProcessed", 0)
                processing = s.get("isProcessing", False)
                print(f"  [LIVE] Samples: {samples} | Frames: {frames} | Processing: {processing}")
        except websocket.WebSocketTimeoutException:
            pass
        except Exception as e:
            print(f"  WS error: {e}")
            time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping processing...")
    ws.send(json.dumps({"type": "stopProcessing", "data": None}))
    time.sleep(1)
    ws.close()
    print("Done")
