# Windows & ESP32-S3 Setup Guide

This guide provides step-by-step instructions for running **Phantom Scan** on a Windows environment and setting up the **ESP32-S3** framework for CSI data capture.

---

## 1. Windows System Setup

### Install Dependencies
Before starting, ensure you have the following installed on your system:
- **Git for Windows**: Download from [git-scm.com](https://git-scm.com/)
- **Python 3**: Download from [python.org](https://www.python.org/downloads/) (Make sure to check "Add Python to PATH" during installation)
- **Node.js**: Download the LTS version (e.g., v18 or v20) from [nodejs.org](https://nodejs.org/). Alternatively, use [nvm-windows](https://github.com/coreybutler/nvm-windows) to manage multiple Node versions.

### Clone and Run Phantom Scan
Open your terminal (Command Prompt or PowerShell) and run:

```cmd
git clone https://github.com/thaerbayyri/Phantom-Scan.git
cd "Phantom-Scan"
npm install
npm run dev
```
The dashboard will be live at `http://localhost:5000`.

---

## 2. ESP32-S3 ESP-IDF Framework Setup

The ESP32-S3 requires the **ESP-IDF** (Espressif IoT Development Framework) to build and flash custom firmware. On Windows, this process is heavily automated by the Espressif Installer.

### Install ESP-IDF
1. Go to the [ESP-IDF Windows Installer Download Page](https://dl.espressif.com/dl/esp-idf/).
2. Download the **ESP-IDF Online Installer** or the **Offline Installer**.
3. Run the installer. It will automatically install all required prerequisites (CMake, Ninja, cross-compiler toolchains, etc.).
4. When finished, it will create shortcut commands like **ESP-IDF X.X CMD** or **ESP-IDF X.X PowerShell** in your Start Menu.

---

## 3. CSI Firmware Setup & Flashing

To capture Channel State Information (CSI), you must flash a CSI-capable firmware to your ESP32-S3.

### Download CSI Firmware Project
Open the **ESP-IDF PowerShell** or **ESP-IDF CMD** shortcut from your Start Menu (this ensures all `idf.py` commands are available). Then run:

```cmd
mkdir %USERPROFILE%\esp
cd %USERPROFILE%\esp
git clone https://github.com/espressif/esp-csi.git
cd esp-csi\examples\get-started\csi_recv
```

### Set Target & Configure
```cmd
idf.py set-target esp32s3
idf.py menuconfig
```
In the config menu:
- Navigate to `Component config` -> `ESP-CSI Configuration`.
- Set the Wi-Fi Channel and Filter Mac as per your target environment.
- Save and exit (press `S` then `Q`).

### Build and Flash
Connect your ESP32-S3 via USB. To find its COM port:
- Right-click the **Start Menu** and open **Device Manager**.
- Expand the **Ports (COM & LPT)** section and look for your ESP32-S3 device (e.g., `COM3`, `COM5`).

```cmd
# Build the firmware
idf.py build

# Flash and open serial monitor (replace COM5 with your actual port)
idf.py -p COM5 flash monitor
```

---

## 4. Connecting ESP32 to Phantom Scan

Once the firmware is flashed and printing CSI data to the serial monitor, use the provided capture script to bridge the data to the Node.js dashboard.

### Run Capture Script
Open a new standard command prompt or PowerShell inside the `phantom scan` directory (where the `scripts` folder is located):

```cmd
cd scripts
python -m venv venv
venv\Scripts\activate
pip install requests pyserial numpy

python csi_capture.py --url http://localhost:5000 --baud 115200 --esp32
```

---

## 🏁 Verification
1. Open `http://localhost:5000` in your browser.
2. Ensure the **Data Source** is set to **Hardware** in the top bar.
3. Observe the real-time **CSI Traces** and **3D Point Cloud** updating as movement is detected.
