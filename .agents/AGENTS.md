# Project Memory & Guidelines: Phantom Scan

This file serves as the persistent memory of the **Phantom Scan** project, providing a high-level overview of the system structure, technical concepts, DSP pipeline, API endpoints, hardware specs, and coding guidelines.

## 1. Project Mission & Capabilities
Phantom Scan is a camera-free human sensing grid utilizing ambient Wi-Fi Channel State Information (CSI) (2.4GHz / 5GHz).
- **Through-Wall Human Tracking** (design goal; through-wall performance is [TO BE MEASURED]): Uses Exponential Moving Average (EMA) background subtraction and 3D Kalman filter tracking.
- **Vital Signs Estimation**: Butterworth filtering, DFT, and phase unwrapping for breathing rate (RPM) and heart rate (BPM) tracking.
- **Directional Mapping (AoA)**: MUSIC (Multiple Signal Classification) algorithm using spatial covariance and eigenvalue decomposition.
- **Distance Ranging**: Power Delay Profile (PDP) via IFFT combined with RSSI log-distance model.
- **Edge Intelligence (WASM)**: High-speed edge DSP and WASM-based hot-swappable inference on ESP32-S3 and server.

## 2. Directory Structure & Core Modules
- [client/](file:///d:/WIFI%20csi/phanotm/phantom%20scan/client): React / TypeScript frontend built with Vite.
  - [src/components/dashboard/](file:///d:/WIFI%20csi/phanotm/phantom%20scan/client/src/components/dashboard): Rich visualization panels (Three.js 3D point cloud, Plotly spectrograms, vitals monitor, control panel, target identity).
- [server/](file:///d:/WIFI%20csi/phanotm/phantom%20scan/server): Express backend serving REST API, WebSockets (`/ws`), and UDP data ingestion.
  - [lib/signal-processing.ts](file:///d:/WIFI%20csi/phanotm/phantom%20scan/server/lib/signal-processing.ts): Implements MUSIC algorithm, Hampel filtering, background subtraction, PDP ranging, Doppler spectrogram.
  - [lib/vitals.ts](file:///d:/WIFI%20csi/phanotm/phantom%20scan/server/lib/vitals.ts): Phase unwrapping and DFT-based heart/breathing rate estimation.
  - [lib/tracking.ts](file:///d:/WIFI%20csi/phanotm/phantom%20scan/server/lib/tracking.ts): DBSCAN clustering of point clouds and 3D Kalman Filter target tracking.
  - [lib/udp-server.ts](file:///d:/WIFI%20csi/phanotm/phantom%20scan/server/lib/udp-server.ts): Binds to port `5005` to ingest packets: Raw CSI (ADR-018) and Edge Vitals (ADR-039).
  - [lib/websocket.ts](file:///d:/WIFI%20csi/phanotm/phantom%20scan/server/lib/websocket.ts): Streams real-time frames (`csiFrame`, `isarFrame`, `vitalSigns`, `pointCloud`, `radialTarget`) to client.
- [shared/](file:///d:/WIFI%20csi/phanotm/phantom%20scan/shared): Contains Zod schemas and TypeScript types defining messages and configs.
- [firmware/esp32-csi-node/](file:///d:/WIFI%20csi/phanotm/phantom%20scan/firmware/esp32-csi-node): Custom ESP-IDF v5.2 firmware for ESP32-S3 to extract and stream CSI. Includes an on-board LVGL display and WebAssembly (WASM) micro-runtime.
- [scripts/](file:///d:/WIFI%20csi/phanotm/phantom%20scan/scripts): Python diagnostics, RF validation, and session reporting.
  - [scripts/reporting/session_reporter.py](file:///d:/WIFI%20csi/phanotm/phantom%20scan/scripts/reporting/session_reporter.py): Runs report compilation (JSON/PDF).

## 3. Signal Processing Pipeline (8-stage)
1. **Raw IQ Data Ingestion**: Receives complex channel responses from antennas.
2. **Hampel Filter**: Removes impulse spikes/outliers.
3. **Background Subtraction**: Uses Exponential Moving Average (EMA) to eliminate static multipath clutter.
4. **Signal Nulling**: Phase-difference cancellation for multipath subtraction.
5. **MUSIC Algorithm**: Angle of Arrival (AoA) estimation via spatial covariance and noise subspace projection.
6. **Vitals Node**: Phase unwrapping and Fourier transform (DFT) in heart rate (0.8–2.0 Hz) and breathing (0.1–0.5 Hz) bands.
7. **PDP Ranger**: Computes distance profiles via Inverse Fast Fourier Transform (IFFT).
8. **Doppler Spectrogram**: Velocity/motion classification (human vs mechanical).

## 4. REST & WebSocket Endpoints
- **REST**:
  - `GET /api/status`: General system stats.
  - `GET /api/v1/system/interfaces`: Lists network adapters.
  - `POST /api/v1/system/execute-task`: Spawns whitelisted shell tasks (e.g. airmon-ng, systemctl restart).
  - `GET /api/v1/diagnostic/stream`: Server-Sent Events stream for system logs.
  - `POST /api/esp32/configure`: Sets active/passive monitor parameters.
  - `GET /api/recording/download`: Serves CSV/JSON/PDF reports.
  - `GET /api/sessions`: List session metadata.
- **WebSocket (`/ws`)**:
  - Streams frames of type `status`, `csiFrame`, `isarFrame`, `pointCloud`, `radialTarget`, `vitalSigns`, etc.
  - Receives control commands like `startProcessing`, `stopProcessing`, `updateConfig`, `startRecording`.

## 5. Development & Deployment Rules (Windows/WSL)
- **PowerShell Direct Execution**: All commands must run directly in PowerShell (no `cmd.exe /c` or wrappers).
- **WSL Hardware Bridge**: Since ESP32-S3 uses USB-OTG, bind to WSL via `usbipd-win` and run diagnostics through `wsl -d Ubuntu --` wrapper.
- **Development Port**: Port `5000` is the single open port. Express hosts both API and Vite development assets on this port.
