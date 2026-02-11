#!/usr/bin/env python3
"""
Phantom Scan CSI Capture Script Template

This script captures CSI (Channel State Information) data from your Wi-Fi hardware
and streams it to the Phantom Scan Dashboard for visualization and processing.

SUPPORTED HARDWARE:
- Intel Wi-Fi 6 AX201 (requires PicoScenes or custom firmware)
- Intel 5300 (with Linux CSI Tool)
- ESP32 (with ESP-IDF CSI)
- USRP SDR (with UHD)

INSTALLATION:
1. Install Python dependencies:
   pip install requests numpy

2. Configure your CSI extraction tool for your hardware

3. Run this script:
   python csi_capture.py --server http://localhost:5000

USAGE:
  python csi_capture.py [OPTIONS]

OPTIONS:
  --server URL      Dashboard server URL (default: http://localhost:5000)
  --rate RATE       Sample rate in Hz (default: 20)
  --demo            Run in demo mode with simulated data
  --file FILE       Read samples from CSV/JSON file instead of hardware
"""

import argparse
import json
import math
import random
import sys
import time
from typing import Dict, Any, List, Optional

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


class CSISample:
    """Represents a single CSI sample."""
    
    def __init__(
        self,
        h1_re: float,
        h1_im: float,
        h2_re: float,
        h2_im: float,
        timestamp: Optional[float] = None,
        rssi: Optional[float] = None,
        subcarrier_index: Optional[int] = None
    ):
        self.timestamp = timestamp or time.time() * 1000  # milliseconds
        self.h1 = {"re": h1_re, "im": h1_im}
        self.h2 = {"re": h2_re, "im": h2_im}
        self.rssi = rssi
        self.subcarrier_index = subcarrier_index
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "timestamp": self.timestamp,
            "h1": self.h1,
            "h2": self.h2,
        }
        if self.rssi is not None:
            result["rssi"] = self.rssi
        if self.subcarrier_index is not None:
            result["subcarrierIndex"] = self.subcarrier_index
        return result


class DemoCSIGenerator:
    """Generates simulated CSI data for testing."""
    
    def __init__(self):
        self.phase = 0
        self.motion_phase = 0
    
    def generate_sample(self) -> CSISample:
        """Generate a simulated CSI sample with realistic motion patterns."""
        # Simulate moving target
        self.motion_phase += 0.02 + random.uniform(-0.005, 0.005)
        target_angle = 20 * math.sin(self.motion_phase)  # degrees
        
        # Convert to channel response
        self.phase += 0.1
        base_amplitude = 0.8 + 0.2 * math.sin(self.phase * 0.3)
        
        # h1: static + dynamic component
        h1_re = base_amplitude * math.cos(self.phase)
        h1_im = base_amplitude * math.sin(self.phase)
        
        # h2: phase shifted based on AoA
        phase_shift = math.radians(target_angle) * 2
        h2_re = base_amplitude * 0.9 * math.cos(self.phase + phase_shift)
        h2_im = base_amplitude * 0.9 * math.sin(self.phase + phase_shift)
        
        # Add noise
        noise = 0.05
        h1_re += random.gauss(0, noise)
        h1_im += random.gauss(0, noise)
        h2_re += random.gauss(0, noise)
        h2_im += random.gauss(0, noise)
        
        return CSISample(
            h1_re=h1_re,
            h1_im=h1_im,
            h2_re=h2_re,
            h2_im=h2_im,
            rssi=-50 + random.gauss(0, 3)
        )


class FileCSIReader:
    """Reads CSI samples from CSV or JSON files."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.samples: List[CSISample] = []
        self.index = 0
        self._load()
    
    def _load(self):
        """Load samples from file."""
        if self.filepath.endswith(".json"):
            self._load_json()
        elif self.filepath.endswith(".csv"):
            self._load_csv()
        else:
            raise ValueError(f"Unsupported file format: {self.filepath}")
        
        print(f"Loaded {len(self.samples)} samples from {self.filepath}")
    
    def _load_json(self):
        """Load from JSON file."""
        with open(self.filepath, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, list):
            for item in data:
                self.samples.append(CSISample(
                    h1_re=item["h1"]["re"],
                    h1_im=item["h1"]["im"],
                    h2_re=item["h2"]["re"],
                    h2_im=item["h2"]["im"],
                    timestamp=item.get("timestamp"),
                    rssi=item.get("rssi"),
                    subcarrier_index=item.get("subcarrierIndex")
                ))
    
    def _load_csv(self):
        """Load from CSV file (format: timestamp,h1_re,h1_im,h2_re,h2_im[,rssi])."""
        with open(self.filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                parts = line.split(",")
                if len(parts) >= 5:
                    self.samples.append(CSISample(
                        timestamp=float(parts[0]),
                        h1_re=float(parts[1]),
                        h1_im=float(parts[2]),
                        h2_re=float(parts[3]),
                        h2_im=float(parts[4]),
                        rssi=float(parts[5]) if len(parts) > 5 else None
                    ))
    
    def get_sample(self) -> Optional[CSISample]:
        """Get next sample, looping if needed."""
        if not self.samples:
            return None
        
        sample = self.samples[self.index]
        self.index = (self.index + 1) % len(self.samples)
        
        # Update timestamp to current time
        sample.timestamp = time.time() * 1000
        return sample


class IntelAX201Capture:
    """
    Capture CSI from Intel AX201 using PicoScenes or similar tools.
    
    NOTE: Direct CSI extraction from AX201 requires:
    - PicoScenes software (https://ps.zpj.io/)
    - Modified firmware or monitor mode support
    - Root/admin privileges
    
    This is a template - implement the actual capture logic based on your setup.
    """
    
    def __init__(self):
        self.initialized = False
        print("Intel AX201 capture template initialized")
        print("NOTE: Implement actual capture logic in get_sample() method")
    
    def initialize(self) -> bool:
        """Initialize hardware capture."""
        # TODO: Add your hardware initialization code here
        # Example for PicoScenes:
        # - Start PicoScenes capture process
        # - Configure interface and channel
        # - Set up CSI extraction parameters
        
        print("Hardware initialization placeholder")
        self.initialized = True
        return True
    
    def get_sample(self) -> Optional[CSISample]:
        """
        Capture a CSI sample from hardware.
        
        Implement this method based on your CSI extraction tool:
        
        For PicoScenes:
            - Read from PicoScenes output pipe/socket
            - Parse the CSI matrix from the packet
            - Extract h1, h2 from the CSI matrix
        
        For Linux CSI Tool:
            - Read from /dev/csi_debug
            - Parse Intel 5300 CSI format
        
        For ESP32:
            - Read from serial/UART
            - Parse ESP-IDF CSI format
        """
        if not self.initialized:
            return None
        
        # Placeholder: Return None to indicate not implemented
        # Replace this with actual capture code
        return None


def send_sample(server_url: str, sample: CSISample, session: requests.Session) -> bool:
    """Send a CSI sample to the dashboard server."""
    try:
        response = session.post(
            f"{server_url}/api/csi/ingest",
            json=sample.to_dict(),
            timeout=1.0
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error sending sample: {e}")
        return False


def send_batch(server_url: str, samples: List[CSISample], session: requests.Session) -> bool:
    """Send a batch of CSI samples to the dashboard server."""
    try:
        response = session.post(
            f"{server_url}/api/csi/ingest/batch",
            json={"samples": [s.to_dict() for s in samples]},
            timeout=2.0
        )
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"Error sending batch: {e}")
        return False


def check_server(server_url: str, session: requests.Session) -> bool:
    """Check if dashboard server is running."""
    try:
        response = session.get(f"{server_url}/api/health", timeout=5.0)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Wi-Vi CSI Capture Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--server",
        default="http://localhost:5000",
        help="Dashboard server URL (default: http://localhost:5000)"
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=20,
        help="Sample rate in Hz (default: 20)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run in demo mode with simulated data"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Read samples from CSV/JSON file"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Number of samples per batch (default: 1)"
    )
    
    args = parser.parse_args()
    
    # Create HTTP session for connection reuse
    session = requests.Session()
    
    # Check server connection
    print(f"Connecting to dashboard server: {args.server}")
    if not check_server(args.server, session):
        print("ERROR: Cannot connect to dashboard server")
        print("Make sure the Wi-Vi Dashboard is running")
        sys.exit(1)
    print("Connected successfully!")
    
    # Select data source
    if args.file:
        print(f"Reading samples from file: {args.file}")
        source = FileCSIReader(args.file)
        get_sample = source.get_sample
    elif args.demo:
        print("Running in demo mode with simulated data")
        source = DemoCSIGenerator()
        get_sample = source.generate_sample
    else:
        print("Initializing hardware capture...")
        source = IntelAX201Capture()
        if not source.initialize():
            print("ERROR: Failed to initialize hardware")
            print("Try running with --demo flag to test with simulated data")
            sys.exit(1)
        get_sample = source.get_sample
    
    # Calculate interval
    interval = 1.0 / args.rate
    
    print(f"Starting capture at {args.rate} Hz (interval: {interval*1000:.1f}ms)")
    print("Press Ctrl+C to stop\n")
    
    samples_sent = 0
    errors = 0
    batch_buffer: List[CSISample] = []
    
    try:
        while True:
            start_time = time.time()
            
            # Get sample
            sample = get_sample()
            if sample is None:
                if not args.demo and not args.file:
                    print("No sample from hardware - implement capture logic")
                    time.sleep(1)
                    continue
                continue
            
            # Batch or send immediately
            if args.batch_size > 1:
                batch_buffer.append(sample)
                if len(batch_buffer) >= args.batch_size:
                    if send_batch(args.server, batch_buffer, session):
                        samples_sent += len(batch_buffer)
                    else:
                        errors += 1
                    batch_buffer = []
            else:
                if send_sample(args.server, sample, session):
                    samples_sent += 1
                else:
                    errors += 1
            
            # Status update
            if samples_sent % 100 == 0 and samples_sent > 0:
                print(f"Samples sent: {samples_sent}, Errors: {errors}")
            
            # Maintain sample rate
            elapsed = time.time() - start_time
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print(f"\n\nCapture stopped. Total samples sent: {samples_sent}, Errors: {errors}")


if __name__ == "__main__":
    main()
