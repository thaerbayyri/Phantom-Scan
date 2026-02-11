# Local Deployment Guide

This guide explains how to run Phantom Scan locally and connect it to your Wi-Fi hardware for real CSI capture.

## Prerequisites

- Node.js 18+ 
- npm or yarn
- Python 3.8+ (for capture script)
- Wi-Fi hardware with CSI extraction capability

## Supported Hardware

### Intel Wi-Fi 6 AX201

CSI extraction from AX201 typically requires:

1. **PicoScenes** (https://ps.zpj.io/) - Commercial/academic CSI tool
   - Supports Intel AX200/AX201
   - Provides comprehensive CSI extraction
   - Requires license for full features

2. **Linux Monitor Mode** (limited support)
   - May require custom kernel patches
   - Limited CSI availability

### Intel 5300

The classic CSI research platform:

1. Install Linux CSI Tool: https://dhalperi.github.io/linux-80211n-csitool/
2. Configure injection/monitor mode
3. CSI data available at `/dev/csi_debug`

### ESP32

Low-cost option with built-in CSI support:

1. Use ESP-IDF with CSI component
2. Example: https://github.com/espressif/esp-csi
3. Data streamed via serial/UART

### USRP SDR

Full control with Software Defined Radio:

1. Install UHD driver
2. Use GNU Radio or custom capture
3. Full flexibility for Phantom Scan research

## Quick Start

### 1. Clone and Install

```bash
# Clone the repository
git clone <your-repo-url>
cd wivi-dashboard

# Install dependencies
npm install
```

### 2. Start the Dashboard Server

```bash
npm run dev
```

The dashboard will be available at http://localhost:5000

### 3. Set Data Source to Hardware

In the dashboard UI:
1. Click the "Data Source" dropdown in the top bar
2. Select "Hardware"

**Note:** The data source must be changed via the UI. The dashboard will then consume CSI samples from the ingestion queue instead of generating demo data.

### 4. Run the Capture Script

```bash
# Install Python dependencies
pip install requests numpy

# Run in demo mode (simulated data) to test
python scripts/csi_capture.py --demo --server http://localhost:5000

# Run with real hardware (after implementing capture logic)
python scripts/csi_capture.py --server http://localhost:5000
```

## API Endpoints

### POST /api/csi/ingest

Ingest a single CSI sample.

**Request Body:**
```json
{
  "timestamp": 1705300000000,
  "h1": {"re": 0.8, "im": 0.2},
  "h2": {"re": 0.7, "im": -0.3},
  "rssi": -45,
  "subcarrierIndex": 0
}
```

**Response:**
```json
{
  "success": true,
  "queueLength": 5,
  "timestamp": 1705300000100
}
```

### POST /api/csi/ingest/batch

Ingest multiple CSI samples at once (more efficient).

**Request Body:**
```json
{
  "samples": [
    {"timestamp": 1705300000000, "h1": {"re": 0.8, "im": 0.2}, "h2": {"re": 0.7, "im": -0.3}},
    {"timestamp": 1705300000050, "h1": {"re": 0.75, "im": 0.25}, "h2": {"re": 0.65, "im": -0.25}}
  ]
}
```

**Response:**
```json
{
  "success": true,
  "samplesIngested": 2,
  "queueLength": 7,
  "timestamp": 1705300000100
}
```

### GET /api/csi/queue

Check the ingestion queue status.

**Response:**
```json
{
  "queueLength": 10,
  "status": {
    "connected": true,
    "dataSource": "hardware",
    "samplesReceived": 1000,
    "framesProcessed": 1000,
    "lastUpdate": 1705300000000,
    "isProcessing": true
  },
  "timestamp": 1705300000100
}
```

## Implementing Hardware Capture

### For Intel AX201 with PicoScenes

Edit `scripts/csi_capture.py` and implement the `IntelAX201Capture.get_sample()` method:

```python
def get_sample(self) -> Optional[CSISample]:
    # Read CSI packet from PicoScenes
    # Parse the CSI matrix
    # Extract h1, h2 from the first two antennas
    
    # Example pseudo-code:
    # packet = picoscenes.read_packet()
    # csi_matrix = packet.csi
    # h1 = complex(csi_matrix[0, 0])
    # h2 = complex(csi_matrix[1, 0])
    
    return CSISample(
        h1_re=h1.real,
        h1_im=h1.imag,
        h2_re=h2.real,
        h2_im=h2.imag,
        rssi=packet.rssi,
        timestamp=packet.timestamp
    )
```

### For Custom Hardware

Create your own capture class following this pattern:

```python
class MyCustomCapture:
    def initialize(self) -> bool:
        # Setup hardware connection
        return True
    
    def get_sample(self) -> Optional[CSISample]:
        # Read and parse CSI data
        # Return CSISample object
        pass
```

## CSV/JSON File Format

### CSV Format

```csv
# timestamp,h1_re,h1_im,h2_re,h2_im,rssi
1705300000000,0.8,0.2,0.7,-0.3,-45
1705300000050,0.75,0.25,0.65,-0.25,-46
```

### JSON Format

```json
[
  {
    "timestamp": 1705300000000,
    "h1": {"re": 0.8, "im": 0.2},
    "h2": {"re": 0.7, "im": -0.3},
    "rssi": -45
  }
]
```

## Troubleshooting

### "Cannot connect to dashboard server"

- Ensure the dashboard is running: `npm run dev`
- Check the server URL matches your setup
- Firewall may be blocking port 5000

### No data appearing in visualization

1. Check that processing is started (click Start button)
2. Verify data source is set to "Hardware" 
3. Check browser console for WebSocket errors
4. Verify samples are being sent: `curl http://localhost:5000/api/csi/queue`

### High latency or dropped samples

- Reduce sample rate: `--rate 10`
- Use batch mode: `--batch-size 10`
- Check network connectivity

## Performance Tips

1. **Batch samples** - Send 10-20 samples per request for efficiency
2. **Match sample rate** - Dashboard processes at ~20 FPS, higher rates may queue
3. **Local network** - Run capture script and dashboard on same machine
4. **Reduce visualization** - Disable features you don't need via config panel
