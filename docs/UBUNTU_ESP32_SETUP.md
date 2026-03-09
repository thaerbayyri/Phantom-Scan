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

To capture Channel State Information (CSI), you must flash a CSI-capable firmware to your ESP32-S3.

### Download CSI Firmware Project
```bash
cd ~/esp
git clone https://github.com/espressif/esp-csi.git
cd esp-csi/examples/get-started/csi_recv
```

### Set Target & Configure
```bash
idf.py set-target esp32s3
idf.py menuconfig
```
In the config menu:
- Navigate to `Component config` -> `ESP-CSI Configuration`.
- Set the Wi-Fi Channel and Filter Mac as per your target environment.

### Build and Flash
Connect your ESP32-S3 via USB and find its port (e.g., `/dev/ttyUSB0`).

```bash
# Grant permissions to the USB port
sudo chmod 666 /dev/ttyUSB0

# Build and flash
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

---

## 4. Connecting ESP32 to Phantom Scan

Once the firmware is flashing and printing CSI data to the serial monitor, use the provided capture script to bridge it to the dashboard.

### Run Capture Script
In a new terminal (inside the `phantom scan` directory):

```bash
cd scripts
python3 -m venv venv
source venv/bin/activate
pip install requests pyserial numpy

python3 csi_capture.py --url http://localhost:5000 --baud 115200 --esp32
```

---

## 🏁 Verification
1. Open `http://localhost:5000`.
2. Ensure the **Data Source** is set to **Hardware** in the top bar.
3. Observe the real-time **CSI Traces** and **3D Point Cloud** updating as movement is detected.
