# Windows ESP32-S3 Setup Guide (Phantom Scan)

This guide provides a comprehensive walkthrough for setting up the **ESP32-S3** in a Windows environment to capture Channel State Information (CSI) for the **Phantom Scan** project.

---

## 1. Prerequisites

Before installing the ESP-IDF, ensure you have the following installed on your Windows machine:
- **Git for Windows**: Download from [git-scm.com](https://git-scm.com/download/win).
- **Python 3.x**: Ensure "Add Python to PATH" is checked during installation.
- **Visual Studio Code**: Recommended IDE for Windows users.

---

## 2. ESP-IDF Framework Installation

The easiest way to set up the ESP-IDF on Windows is by using the **Espressif Online Installer**.

### Steps:
1. Download the **ESP-IDF Tools Installer** from the [official Espressif website](https://dl.espressif.com/dl/esp-idf/).
2. Run the installer and select the following options:
   - **Installation Type**: `Online`
   - **ESP-IDF Version**: `v5.1` or higher (Recommended).
   - **Target**: `ESP32-S3`
3. The installer will automatically download the required tools (CMake, Ninja, Cross-compilers).
4. Once completed, you will have an **ESP-IDF PowerShell** and **ESP-IDF Command Prompt** on your desktop.

---

## 3. Driver Installation

The ESP32-S3 usually uses a built-in USB-to-Serial converter or an external silicon chip (like CP210x/CH340).

- **S3 Built-in Port**: Windows typically detects this automatically as a "USB Serial Port (COMx)".
- **External Chips**: If your board isn't recognized, download drivers:
  - [CP210x VCP Drivers](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers)
  - [CH340 Drivers](http://www.wch-ic.com/downloads/CH341SER_EXE.html)

Check your device manager under `Ports (COM & LPT)` to identify your COM port (e.g., `COM5`).

---

## 4. CSI Firmware Setup & Flashing

### Clone components
Open the **ESP-IDF PowerShell** (installed in Step 2) and run:

```powershell
mkdir esp
cd esp
git clone https://github.com/espressif/esp-csi.git
cd esp-csi\examples\get-started\csi_recv
```

### Build and Flash
1. **Set target**:
   ```powershell
   idf.py set-target esp32s3
   ```
2. **Configure Channel**:
   ```powershell
   idf.py menuconfig
   # Navigate: Component config -> ESP-CSI Configuration
   # Set the WiFi channel to match your router
   ```
3. **Flash firmware**:
   ```powershell
   idf.py -p COMx flash monitor
   # Replace COMx with your port (e.g., COM5)
   ```

---

## 5. Bridging to Phantom Scan Dashboard

Once the ESP32 is flashing and printing data, you need to bridge that data to the dashboard using Python.

### Setup Python Environment
Open a standard Windows Terminal/PowerShell in the project's root:

```powershell
cd scripts
python -m venv venv
.\venv\Scripts\activate
pip install requests pyserial numpy
```

### Run Capture Script
```powershell
python csi_capture.py --url http://localhost:5000 --baud 115200 --esp32
```

---

## 6. Troubleshooting (Windows-Specific)

- **Port Busy Error**: Ensure no other serial monitors (like Arduino Serial Monitor) are open.
- **Python Path**: If `python` command is not found, ensure it is added to your Environment Variables.
- **WSL Conflict**: If you are running the dashboard in WSL and the capture script in Windows, ensure they can communicate over `localhost` or your internal IP.
- **Permission Denied**: If flashing fails, try running the ESP-IDF PowerShell as Administrator.

---

## 🏁 Verification
1. Launch the Phantom Scan dashboard (`npm run dev`).
2. Set **Data Source** to **Hardware**.
3. Verify that the **CSI Graph** starts populating as the capture script sends data.
