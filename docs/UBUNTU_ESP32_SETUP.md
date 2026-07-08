# Ubuntu & ESP32-S3 Setup Guide

This guide provides step-by-step instructions for running **Phantom Scan** on an Ubuntu OS and setting up the **ESP32-S3** framework for CSI data capture.

---

## 1. Ubuntu System Setup

### Install Dependencies
Open your terminal and run the following commands to install the required system dependencies:

```bash
sudo apt update
sudo apt install -y git curl build-essential python3 python3-pip python3-venv libusb-1.0-0-dev
```

### Install Node.js (via NVM)
It is recommended to use NVM (Node Version Manager) to handle Node.js versions.

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18
```

### Clone and Run Phantom Scan
```bash
git clone https://github.com/thaerbayyri/Phantom-Scan.git
cd "phantom scan"
npm install
npm run dev
```
The dashboard will be live at `http://localhost:5000`.

---

## 2. ESP32-S3 ESP-IDF Framework Setup

The ESP32-S3 requires the **ESP-IDF** (Espressif IoT Development Framework) to build and flash custom firmware.

### Install ESP-IDF Prerequisites
```bash
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
```

### Download and Install ESP-IDF
```bash
mkdir -p ~/esp
cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git
cd ~/esp/esp-idf
./install.sh esp32s3
source ./export.sh
```
> [!TIP]
> Add `alias get_idf='. $HOME/esp/esp-idf/export.sh'` to your `~/.bashrc` to quickly load the environment in new terminals.

---

## 3. CSI Firmware Setup & Flashing

Use the repo's own firmware in `firmware/esp32-csi-node` — not the generic esp-csi
example. It streams CSI over **UDP to the dashboard on port 5005** (no serial bridge).

### Build (from the repository root)
```bash
cd "phantom scan/firmware/esp32-csi-node"
idf.py set-target esp32s3
idf.py build
```
(Or use the Docker build from `firmware/esp32-csi-node/README.md` — the most reliable method.)

### Flash both boards
Connect each ESP32-S3 via USB and find its port (e.g., `/dev/ttyUSB0`, `/dev/ttyUSB1`).

```bash
sudo chmod 666 /dev/ttyUSB0
idf.py -p /dev/ttyUSB0 flash monitor
```

### Provision each board (no reflash needed)
Each board needs the WiFi credentials, the **host PC's stable IP**, and a **unique
node_id**:

```bash
python3 esp-flash.py --port /dev/ttyUSB0 --ssid "YourSSID" --password "YourPass" \
  --target-ip 192.168.1.20 --target-port 5005 --node-id 1
python3 esp-flash.py --port /dev/ttyUSB1 --ssid "YourSSID" --password "YourPass" \
  --target-ip 192.168.1.20 --target-port 5005 --node-id 2
```

Use a **2.4 GHz** SSID on a fixed channel.

---

## 4. Connecting ESP32 to Phantom Scan

Nothing extra to run: the dashboard (`npm run dev`) **is** the UDP ingest and binds
`0.0.0.0:5005` directly. Expected console lines:

```text
[dev-full] starting dashboard on port 5000 (owns UDP :5005 ESP32 ingest)
[UDP] CSI Receiver listening on 0.0.0.0:5005
[UDP] Received 210 packets in last 5s
```

Do **not** run `python -m phantom.runtime live` or
`scripts/ruview-dashboard-bridge.py` at the same time — they also bind `:5005`.

---

## 🏁 Verification
1. Open `http://localhost:5000` and log in.
2. Confirm `[UDP] Received N packets in last 5s` in the dashboard console.
3. Both node beacons active; walking between the boards slides the target along the
   node axis (`fused_two_node`).
4. The **Board DSP** card shows per-node firmware metrics (presence, motion,
   respiration, heart rate) refreshing about once per second.
