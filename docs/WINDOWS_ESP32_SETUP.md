# Windows ESP32-S3 Setup Guide (Phantom Scan)

This guide walks through setting up the **ESP32-S3** nodes on Windows for the
**Phantom Scan** project using the repo's own firmware (`firmware/esp32-csi-node`).
The boards stream CSI over **UDP to the dashboard on port 5005** — there is no serial
bridging in the supported path.

---

## 1. Prerequisites

- **Git for Windows**: [git-scm.com](https://git-scm.com/download/win)
- **Python 3.x** with `pip install esptool` (flashing + provisioning)
- **Docker Desktop** (the firmware README's Docker build is the only reliable build method)
- **Node.js** (for the dashboard: `npm run dev`)

---

## 2. Driver Installation

The ESP32-S3 dev boards used in this project enumerate via a **CH343** USB-serial chip
(shows as `USB-Enhanced-SERIAL CH343 (COMx)` in Device Manager). Others use CP210x/CH340
or the S3's built-in USB port.

- [CH343/CH340 Drivers](http://www.wch-ic.com/downloads/CH341SER_EXE.html)
- [CP210x VCP Drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)

Check `Ports (COM & LPT)` in Device Manager to identify each board's COM port
(e.g. node 1 on `COM5`, node 2 on `COM6`).

---

## 3. Build the Firmware (Docker)

From the repository root in Git Bash or PowerShell:

```bash
MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$(pwd)/firmware/esp32-csi-node:/project" -w /project \
  espressif/idf:v5.2 bash -c \
  "rm -rf build sdkconfig && idf.py set-target esp32s3 && idf.py build"
```

(Alternative: an ESP-IDF v5.2 PowerShell with `idf.py set-target esp32s3 && idf.py build`
inside `firmware\esp32-csi-node`.)

---

## 4. Flash Both Boards

```powershell
python -m esptool --chip esp32s3 --port COM5 --baud 460800 `
  write_flash --flash_mode dio --flash_size 8MB `
  0x0 firmware/esp32-csi-node/build/bootloader/bootloader.bin `
  0x8000 firmware/esp32-csi-node/build/partition_table/partition-table.bin `
  0x10000 firmware/esp32-csi-node/build/esp32-csi-node.bin
```

Repeat with `--port COM6` for the second board. App-only reflashes preserve the NVS
provisioning written in the next step.

---

## 5. Provision Each Board (no reflash needed)

`esp-flash.py` writes WiFi credentials and the aggregator target into NVS. Each board
needs a **unique `node_id`** and the **host PC's IP** (must be stable — set a DHCP
reservation):

```powershell
cd firmware\esp32-csi-node
python esp-flash.py --port COM5 --ssid "YourSSID" --password "YourPass" `
  --target-ip 192.168.1.20 --target-port 5005 --node-id 1
python esp-flash.py --port COM6 --ssid "YourSSID" --password "YourPass" `
  --target-ip 192.168.1.20 --target-port 5005 --node-id 2
```

Use a **2.4 GHz** SSID on a fixed channel. Duplicate `node_id` values make the host
reject one board as a source-mismatch spoof.

---

## 6. Run the Dashboard

The dashboard **is** the UDP ingest — no capture script or bridge is needed:

```powershell
npm run dev
```

Expected console lines:

```text
[dev-full] starting dashboard on port 5000 (owns UDP :5005 ESP32 ingest)
[UDP] CSI Receiver listening on 0.0.0.0:5005
[UDP] Received 210 packets in last 5s
```

Do **not** run `python -m phantom.runtime live` or
`scripts/ruview-dashboard-bridge.py` at the same time — they also bind `:5005`.

---

## 7. Troubleshooting (Windows-Specific)

- **Port Busy Error (COM)**: close any other serial monitors before flashing.
- **`[UDP] Cannot bind UDP :5005`**: another ingest (Python authority or RuView bridge)
  holds the port — stop it.
- **Boards silent on UDP**: verify serial logs show WiFi connect,
  `self-ping started -> <gw> @50Hz`, and non-zero `medium tick: yield=…`; check the
  provisioned `--target-ip` matches the host's current IP.
- **Permission Denied while flashing**: run the shell as Administrator.

---

## 🏁 Verification

1. `npm run dev` → open `http://localhost:5000`, log in.
2. Confirm `[UDP] Received N packets in last 5s` in the console.
3. Both node beacons active in the radar; walking between the boards slides the target
   along the node axis (`fused_two_node`).
4. The **Board DSP** card shows per-node firmware metrics (presence, motion,
   respiration, heart rate) refreshing about once per second.
