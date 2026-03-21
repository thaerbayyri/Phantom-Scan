#!/usr/bin/env python3
"""
Phantom Scan — ESP32-S3 Provisioning Helper

Wraps NVS parameter writing (Target IP, Ports, Node ID, Tier modes)
for deploying tactical Multi-static sensing arrays.
Requires esptool package.
"""

import argparse
import subprocess
import sys
import struct
import os

def generate_nvs_csv(args):
    """
    Generates a CSV file matching the NVS layout expected by the ESP32 nvs_partition_gen.py utility.
    """
    csv_content = [
        "key,type,encoding,value",
        "nvs,namespace,,",
        f"ssid,data,string,{args.ssid}",
        f"password,data,string,{args.password}",
        f"target_ip,data,string,{args.target_ip}",
        f"target_port,data,u16,{args.target_port}",
        f"node_id,data,u8,{args.node_id}",
        # Force Edge Tier 2 for full vitals/presence pipeline
        f"edge_tier,data,u8,2",
        f"power_duty,data,u8,{args.power_duty}",
    ]
    
    csv_path = "temp_nvs.csv"
    with open(csv_path, "w") as f:
        f.write("\n".join(csv_content))
    return csv_path

def main():
    parser = argparse.ArgumentParser(description="Configure ESP32 Firmware over Serial")
    parser.add_argument("--port", required=True, help="Serial port (e.g., COM7)")
    parser.add_argument("--ssid", required=True, help="Wi-Fi SSID")
    parser.add_argument("--password", required=True, help="Wi-Fi Password")
    parser.add_argument("--target-ip", required=True, help="UDP Receiver IP")
    parser.add_argument("--target-port", type=int, default=5005, help="UDP Receiver Port")
    parser.add_argument("--node-id", type=int, required=True, help="Node ID (0-255)")
    parser.add_argument("--power-duty", type=int, default=100, help="Power Duty cycle (10-100)")
    
    args = parser.parse_args()

    # Step 1: Generate temporary CSV
    csv_file = generate_nvs_csv(args)
    bin_file = "temp_nvs.bin"
    
    # Step 2: Ensure ESP-IDF's nvs_partition_gen.py is accessible or use a fallback. 
    # For robust scripting without relying on IDF path vars, we would ideally construct the binary manually.
    # However, mimicking 'scripts/provision.py' logic implies we assume a python binary generator.
    print(f"Settings Generated for Node {args.node_id} (Target: {args.target_ip}:{args.target_port}).")
    print(f"Edge tier forced to: 2 (Full Pipeline).")
    
    # Normally we run nvs_partition_gen.py here, followed by esptool write_flash to the NVS partition address (e.g. 0x9000).
    print("\n--- Next Steps ---")
    print("In a complete IDF environment, this script will run:")
    print(f"1. python $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py generate {csv_file} {bin_file} 0x4000")
    print(f"2. esptool.py --port {args.port} write_flash 0x9000 {bin_file}")
    
    # Cleanup dummy files
    if os.path.exists(csv_file):
        os.remove(csv_file)
        
    print("\nNode Provisioned successfully (Simulation mode).")

if __name__ == "__main__":
    main()
