# Phantom Scan

**Real-time Wi-Fi CSI Signal Processing Dashboard for Through-Wall Human Detection & Tracking**

Phantom Scan processes Channel State Information (CSI) from Wi-Fi signals to detect, classify, and track human movement through walls using advanced radar signal processing algorithms (MUSIC, ISAR, Doppler analysis). The system runs a full-stack web dashboard with real-time 3D visualization, powered by an Express/WebSocket backend and a React/TypeScript frontend.

---

## Table of Contents

- [What It Does](#what-it-does)
- [System Architecture & Methodology](#system-architecture--methodology)
- [Signal Processing Pipeline](#signal-processing-pipeline)
- [File Hierarchy](#file-hierarchy)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)

---

## What It Does

| Capability | Description |
|---|---|
| **Through-Wall Sensing** | Processes Wi-Fi CSI to detect people behind walls using signal reflections |
| **Angle of Arrival (AoA)** | Determines the direction of a target using the MUSIC algorithm |
| **Human Tracking** | Clusters point clouds (DBSCAN) and smooths trajectories (Kalman Filter) |
| **Human vs Machine Classification** | Uses Micro-Doppler spectral analysis to distinguish human and mechanical motion |
| **Gesture Recognition** | Detects binary gestures (forward/backward motion) via matched-filter correlation |
| **Distance Estimation** | Uses Power Delay Profile (IFFT) + RSSI log-distance model to range targets |
| **Doppler Spectrogram** | Visualizes velocity signatures over time via sliding-window DFT |
| **Real-Time Dashboard** | Streams all data over WebSocket to a React dashboard with 3D plots |
| **CSI Recording** | Records sessions to CSV for offline analysis |

---

## System Architecture & Methodology

### Design Methodology

The project follows a **modular, pipeline-oriented architecture** with clear separation between:

1. **Data Ingestion Layer** — Captures raw CSI from hardware (ESP32-S3 via serial) or generates demo data
2. **Signal Processing Pipeline** — Multi-stage DSP chain that transforms raw CSI into actionable intelligence
3. **Tracking & Classification Layer** — Clusters detections and tracks targets with state estimation
4. **Real-Time Transport Layer** — WebSocket server that streams processed frames to all connected clients
5. **Visualization Layer** — React dashboard with Plotly.js charts for real-time rendering

### Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, TypeScript, Plotly.js, Three.js, Tailwind CSS, shadcn/ui (Radix UI) |
| **Backend** | Node.js, Express, TypeScript (ESM), WebSocket (ws) |
| **Validation** | Zod schemas for all data types (shared between client and server) |
| **Hardware Scripts** | Python 3 (pyserial, numpy, scipy, pywt, scikit-learn) |
| **Build** | Vite, esbuild, tsx |
| **Routing** | Wouter (lightweight React router) |
| **State Management** | TanStack React Query (server state), React hooks (local state) |

---

## Signal Processing Pipeline

```
Raw CSI (h1, h2)
  │
  ├─→ Hampel Filter ──→ Outlier removal (median/MAD spike detection)
  │
  ├─→ Background Subtractor ──→ Remove static multipath (EMA subtraction)
  │
  ├─→ Signal Nulling ──→ Precoding ratio p = -h1/h2 to cancel static path
  │
  ├─→ MUSIC Algorithm ──→ AoA spectrum via eigendecomposition (noise subspace)
  │     └── Power Iteration for eigenvector extraction
  │
  ├─→ AoA → Point Cloud ──→ Convert angle + amplitude → 3D coordinates
  │
  ├─→ DBSCAN Clustering ──→ Group point cloud into target clusters
  │
  ├─→ Kalman Filter ──→ Smooth trajectory, predict during occlusion
  │
  ├─→ Motion Gate ──→ Variance-based motion detection with auto-calibration
  │
  ├─→ Micro-Doppler Classifier ──→ FFT-based human vs mechanical discrimination
  │
  ├─→ PDP Ranger ──→ IFFT Power Delay Profile for distance estimation
  │
  ├─→ Doppler Computer ──→ Sliding-window DFT for velocity spectrogram
  │
  └─→ Gesture Detector ──→ Matched-filter correlation on centroid shifts
        └── Templates: Bit 0 (forward-backward), Bit 1 (backward-forward)
```

---

## File Hierarchy

```
phantom-scan/
│
├── server/                         # ── Express + WebSocket Backend ──
│   ├── index.ts                    # App entry: Express setup, middleware, port binding
│   ├── routes.ts                   # REST API endpoints (status, config, CSI ingest, recording)
│   ├── vite.ts                     # Vite dev server integration (HMR proxy)
│   ├── static.ts                   # Production static file serving
│   ├── storage.ts                  # In-memory user storage interface
│   └── lib/                        # Core signal processing library
│       ├── complex.ts              # Complex number math (add, sub, mul, div, conj, mag, phase, polar, matMul, hermitian)
│       ├── signal-processing.ts    # DSP algorithms (1103 lines) — see breakdown below
│       ├── tracking.ts             # DBSCAN clustering + Kalman filter + TrackingProcessor
│       └── websocket.ts            # SignalProcessingServer — real-time frame processing & broadcast
│
├── client/                         # ── React Frontend ──
│   └── src/
│       ├── main.tsx                # React DOM entry point
│       ├── App.tsx                 # Router: "/" → Dashboard, "*" → 404
│       ├── index.css               # Global styles, Tailwind config, CSS variables (light/dark)
│       ├── react-plotly.d.ts       # TypeScript declaration for react-plotly.js
│       ├── pages/
│       │   ├── dashboard.tsx       # Main dashboard page — assembles all widgets
│       │   └── not-found.tsx       # 404 page
│       ├── hooks/
│       │   ├── use-websocket.ts    # WebSocket hook — connects, parses frames, exposes state & actions
│       │   ├── use-mobile.tsx      # Mobile viewport detection hook
│       │   └── use-toast.ts        # Toast notification system hook
│       ├── lib/
│       │   ├── complex.ts          # Client-side complex number utilities
│       │   ├── queryClient.ts      # TanStack React Query client config
│       │   └── utils.ts            # Tailwind class merge utility (cn)
│       └── components/
│           ├── theme-toggle.tsx    # Light/dark mode toggle button
│           ├── ui/                 # shadcn/ui component library (48 Radix UI primitives)
│           └── dashboard/          # Dashboard-specific visualization widgets
│               ├── top-bar.tsx             # Header: status, data source selector, start/stop, recording
│               ├── control-panel.tsx       # DSP parameter controls (nulling, MUSIC, gesture, clutter)
│               ├── RadialScene.tsx         # 3D radar scene with ESP32-centric coordinate grid
│               ├── DirectionalNode.tsx     # Animated 3D human mesh with direction indicator
│               ├── HumanMesh.tsx           # Three.js human figure with walking animation
│               ├── MachineStatic.tsx       # Three.js static mechanical target visualization
│               ├── point-cloud-3d.tsx      # 3D point cloud wrapper using React Three Fiber
│               ├── aoa-spectrum.tsx        # AoA line chart (angle vs power)
│               ├── aoa-heatmap.tsx         # Time × Angle heatmap (Plotly.js)
│               ├── doppler-spectrogram.tsx # Time × Frequency velocity spectrogram
│               ├── gesture-log.tsx         # Gesture event log with bit classification
│               ├── metrics-panel.tsx       # Numeric metrics: precoding ratio, peak angle/power
│               ├── target-identity-card.tsx# Human/Mechanical classification display
│               ├── distance-meter.tsx      # Distance gauge (PDP + wall reflection)
│               ├── signal-traces.tsx       # Multi-line signal amplitude chart
│               └── signal-avatar.tsx       # Signal strength avatar component
│
├── shared/                         # ── Shared TypeScript Types ──
│   └── schema.ts                   # Zod schemas & TypeScript types for ALL data structures
│
├── scripts/                        # ── Python Hardware & Analysis Scripts ──
│   ├── csi_capture.py              # ESP32-S3 serial capture → REST API ingestion to dashboard
│   ├── csi_filter_pipeline.py      # Offline Python DSP pipeline (Hampel, DWT, MUSIC, DBSCAN, Kalman)
│   └── tracking_processor.py       # Standalone DBSCAN + Kalman tracking processor
│
├── recordings/                     # Saved CSI session CSV files
├── docs/
│   └── LOCAL_DEPLOYMENT.md         # Local deployment & hardware setup guide
├── script/
│   └── build.ts                    # Production build script (esbuild bundling)
│
├── package.json                    # Node.js dependencies & scripts
├── tsconfig.json                   # TypeScript compiler configuration
├── vite.config.ts                  # Vite build & dev server config
├── tailwind.config.ts              # Tailwind CSS theme config with custom design tokens
├── postcss.config.js               # PostCSS plugin config
├── drizzle.config.ts               # Drizzle ORM database config
├── components.json                 # shadcn/ui component library config
├── design_guidelines.md            # UI/UX design guidelines
├── README.md                       # This file
└── .gitignore                      # Git ignore rules
```

---

## Key Files & Their Functions

### `server/lib/signal-processing.ts` (1103 lines)

The core DSP engine containing all signal processing algorithms:

| Class / Function | Purpose |
|---|---|
| `calculatePrecodingRatio(h1, h2)` | Computes nulling ratio `p = -h1/h2` |
| `applyNulling(sample, config)` | Removes static reflections using precoding |
| `powerIterationEigen(R, iterations)` | Eigendecomposition via power iteration for MUSIC |
| `computeMUSICSpectrum(samples, ...)` | MUSIC algorithm — AoA pseudo-spectrum from noise subspace |
| `findSpectrumPeak(spectrum)` | Finds peak angle/power in AoA spectrum |
| `aoaToPoint(aoa, amplitude, ...)` | Converts AoA + amplitude to 3D Cartesian coordinates |
| `normalizeTemplate(template)` | Normalizes gesture matched-filter templates |
| `matchedFilterCorrelation(signal, template)` | Cross-correlation for gesture detection |
| **`GestureDetector`** | Detects Bit 0/1 gestures using centroid shift correlation |
| **`HeatmapAccumulator`** | Builds time × angle intensity maps from AoA spectra |
| **`HampelFilter`** | Median/MAD outlier removal for noisy CSI samples |
| **`MicroDopplerClassifier`** | FFT-based human vs mechanical motion discrimination |
| **`PDPRanger`** | IFFT Power Delay Profile for target distance estimation + RSSI log-distance |
| **`BackgroundSubtractor`** | Sliding-window mean subtraction to remove static clutter |
| **`MotionGate`** | Variance-based motion detection with auto-calibrating noise floor |
| **`DopplerComputer`** | Sliding-window DFT for velocity spectrogram generation |
| **`CSIDataParser`** | Parses JSON CSI data from ESP32/USRP hardware |
| **`DemoDataGenerator`** | Generates synthetic CSI data with simulated human movement |

### `server/lib/tracking.ts` (360 lines)

| Class | Purpose |
|---|---|
| **`DBSCAN`** | Density-based spatial clustering (eps, minPts) to group point cloud detections |
| **`KalmanFilter`** | 6-state constant-velocity Kalman filter (x, y, z, vx, vy, vz) with 3×3 matrix inversion |
| **`TrackingProcessor`** | Orchestrates DBSCAN → largest cluster → Kalman update, coasts during occlusion |

### `server/lib/websocket.ts` (652 lines)

| Method | Purpose |
|---|---|
| `initialize(server)` | Creates WebSocket server, handles client connections |
| `handleMessage(clientId, message)` | Processes client commands (start, stop, config, recording) |
| `startProcessing()` / `stopProcessing()` | Controls the 50ms frame processing loop |
| `processFrame()` | **Main loop**: generates/fetches CSI → pipeline → broadcast results |
| `updateConfig(updates)` | Updates DSP parameters at runtime |
| `setDataSource(source)` | Switches between demo, hardware, ESP32 modes |
| `startRecording()` / `stopRecording()` | CSV session recording control |
| `ingestSample(sample)` / `ingestSamples(batch)` | Accepts CSI from external capture scripts |
| `broadcast(type, data)` | Sends processed frames to all connected clients |

### `server/routes.ts` — REST API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/status` | GET | System status (processing state, frame count) |
| `/api/config` | GET | Current DSP configuration |
| `/api/health` | GET | Health check |
| `/api/csi/ingest` | POST | Ingest single CSI sample from hardware |
| `/api/csi/ingest/batch` | POST | Ingest batch of CSI samples |
| `/api/csi/queue` | GET | Check ingestion queue length |
| `/api/recording/download` | GET | Download last recorded CSV session |

### `shared/schema.ts` — Data Types (Zod + TypeScript)

Defines all data structures shared between client and server:

`ComplexNumber` · `CSISample` · `ChannelEstimate` · `AoASpectrumPoint` · `ISARFrame` · `PointCloudPoint` · `GestureEvent` · `HeatmapData` · `MotionStatus` · `DopplerFrame` · `RecordingStatus` · `ProcessingConfig` · `DataSource` · `SystemStatus` · `TrackedTarget` · `RadialTarget` · `TargetIdentity` · `SignalTrace` · `StreamFrame`

### `client/src/hooks/use-websocket.ts` — Client WebSocket Hook

The central React hook that manages the entire client-side state:
- Establishes WebSocket connection with auto-reconnect (2s interval)
- Parses incoming frames by type and updates React state
- Exposes actions: `startProcessing`, `stopProcessing`, `updateConfig`, `setDataSource`, `startRecording`, `stopRecording`

### `scripts/csi_capture.py` — Hardware Capture Script

Reads ESP32-S3 CSI data over serial USB and streams it to the dashboard:
- Auto-detects COM ports, configurable baud rate (921600 default)
- Parses two formats: raw CSV and ESP-CSI protocol
- Batches samples (10/batch) and POSTs to `/api/csi/ingest/batch`
- Polls `/api/status` to pause/resume capture when dashboard processing stops

### `scripts/csi_filter_pipeline.py` — Offline Python DSP Pipeline

Full Python implementation of the signal processing chain for offline analysis:

| Class | Purpose |
|---|---|
| **`HampelFilter`** | Same as TypeScript version — outlier removal via median/MAD |
| **`DWTDenoiser`** | Discrete Wavelet Transform soft-thresholding (db4 wavelet) |
| **`BackgroundSubtractor`** | EMA-based static multipath removal |
| **`KalmanTracker`** | 2D constant-velocity Kalman filter (x, z, vx, vz) |
| **`CSIFilterPipeline`** | Orchestrates the full pipeline: Hampel → DWT → Background Sub → STFT → PDP → AoA → DBSCAN → Kalman |

### `scripts/tracking_processor.py` — Standalone Tracking

Python implementation of DBSCAN + Kalman tracking with CSV export, used for offline processing.

---

## Getting Started

### Prerequisites

- **Node.js** v18+ ([download](https://nodejs.org/))
- **Python 3.11+** (only for hardware capture scripts)
- **ESP32-S3** with CSI firmware (for live data — demo mode works without hardware)

### Installation

```bash
# Clone the repo
git clone https://github.com/thaerbayyri/Phantom-Scan.git
cd phantom-scan

# Install Node.js dependencies
npm install

# (Optional) Install Python dependencies for hardware capture
pip install pyserial requests numpy scipy pywt scikit-learn
```

### Running the Dashboard

```bash
# Start the dev server (serves both API and frontend)
npm run dev
```

Open **http://localhost:5000** in your browser. The dashboard starts in **demo mode** with synthetic CSI data — no hardware required.

### Connecting ESP32-S3 Hardware

```bash
# In a second terminal, start the capture script
python scripts/csi_capture.py --url http://localhost:5000 --baud 921600
```

Then switch the data source to **"Hardware"** in the dashboard top bar.

### Keyboard Shortcuts

| Key | Action |
|---|---|
| `Space` | Start / Stop processing |
| `R` | Reload dashboard |

---

## API Reference

### WebSocket Messages (Port 5000)

**Client → Server:**
| Type | Data | Action |
|---|---|---|
| `start` | — | Begin frame processing |
| `stop` | — | Stop frame processing |
| `config` | `Partial<ProcessingConfig>` | Update DSP parameters |
| `setDataSource` | `DataSource` | Switch data source |
| `startRecording` | — | Begin CSV recording |
| `stopRecording` | — | Stop recording |

**Server → Client:**
| Type | Data | Description |
|---|---|---|
| `status` | `SystemStatus` | Processing state update |
| `csiFrame` | `ChannelEstimate` | Raw + nulled channel estimates |
| `isarFrame` | `ISARFrame` | AoA spectrum + peak |
| `pointCloud` | `PointCloudPoint[]` | 3D detection points |
| `gesture` | `GestureEvent` | Detected gesture (Bit 0/1) |
| `heatmap` | `HeatmapData` | Time × Angle intensity map |
| `motionStatus` | `MotionStatus` | Motion detection status |
| `dopplerFrame` | `DopplerFrame` | Velocity spectrogram data |
| `trackedTarget` | `TrackedTarget` | Kalman-filtered 3D target state |
| `radialTarget` | `RadialTarget` | ESP-centric radial coordinate target |
| `targetIdentity` | `TargetIdentity` | Human/mechanical classification result |
| `recordingStatus` | `RecordingStatus` | Recording state update |

---

## License

MIT
