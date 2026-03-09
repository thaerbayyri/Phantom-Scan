# WSL USB Setup Guide

To interface with the physical USB sensor from the Phantom Scan backend running inside the Windows Subsystem for Linux (WSL), you must bind the USB device from the Windows host into the WSL Ubuntu instance.

We use `usbipd-win` to achieve this passthrough.

## 1. Prerequisites

1. **Install Ubuntu on WSL:**
   Open an Administrator PowerShell prompt and run:
   ```powershell
   wsl --install -d Ubuntu
   ```
   *Restart your computer if prompted.*

2. **Install usbipd-win on Windows:**
   Install `usbipd-win` using the Windows Package Manager (winget) from an Administrator PowerShell console:
   ```powershell
   winget install --interactive --exact dorssel.usbipd-win
   ```
   *Note: Close and reopen your terminal after installation to ensure the `usbipd` command is available in your PATH.*

3. **Install User-Space Tools in Ubuntu:**
   Open your WSL Ubuntu terminal and install the USBIP client tools:
   ```bash
   sudo apt update
   sudo apt install linux-tools-virtual hwdata
   sudo update-alternatives --install /usr/local/bin/usbip usbip /usr/lib/linux-tools/*/usbip 20
   ```

## 2. Binding the Hardware Sensor

1. **List available USB devices:**
   Plug in your hardware sensor, then from a Windows PowerShell prompt (with Administrator privileges), run:
   ```powershell
   usbipd list
   ```
   *Example output:*
   ```text
   Connected:
   BUSID  VID:PID    DEVICE                                                        STATE
   2-1    0403:6001  USB Serial Converter                                          Not shared
   ```

2. **Bind the device to usbipd:**
   Identify the `BUSID` of your sensor (e.g., `2-1`). Then run:
   ```powershell
   usbipd bind --busid <busid>
   ```

3. **Attach the device to WSL:**
   Ensure your WSL Ubuntu instance is running, then attach the specific `BUSID`:
   ```powershell
   usbipd attach --wsl --busid <busid>
   ```

## 3. Verification

Inside your WSL Ubuntu terminal, run:
```bash
lsusb
```
You should now see the USB sensor listed in the output, and any diagnostic tools executed within the WSL environment (via our backend secure process spawner) will be able to interface with it seamlessly.
