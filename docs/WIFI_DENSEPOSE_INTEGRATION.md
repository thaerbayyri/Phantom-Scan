> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# WiFi-DensePose Integration in Phantom Scan

This document outlines the theoretical foundation and the specific technical integration of the **WiFi-DensePose** architecture within the Phantom Scan system.

---

## 1. What is WiFi-DensePose?

Traditional **DensePose** (developed by Facebook AI Research) is an algorithm that maps 2D RGB image pixels of humans to a 3D surface model of the human body. 

**WiFi-DensePose** takes this concept into the RF (Radio Frequency) domain. Instead of using optical cameras, it relies entirely on the microscopic scattering, reflection, and diffraction of ambient Wi-Fi radio waves bouncing off human bodies. By analyzing the **Channel State Information (CSI)**—specifically the phase and amplitude perturbations across multiple subcarriers and antennas—complex neural networks can reconstruct a dense 3D human pose wireframe. 

**Why it matters:**
*   **Privacy-First:** It completely eliminates cameras, capturing no facial data, skin tone, or clothing details.
*   **Non-Line-of-Sight (NLOS):** 2.4GHz and 5GHz Wi-Fi waves easily penetrate drywall, wooden doors, and concrete blocks, allowing the system to literally "see" human postures through walls.
*   **Illumination Independent:** It works flawlessly in pitch-black conditions or absolute darkness.

---

## 2. How it Works in Phantom Scan

Phantom Scan implements a highly-optimized, edge-compute variant of WiFi-DensePose. The pipeline breaks down into four main stages:

### Stage A: Multistatic CSI Ingestion
To map a 3D pose, the system requires spatial diversity. We deploy 3 to 6 **ESP32-S3** microcontrollers around a room. These nodes are placed in monitor mode and tuned to a specific network (SSID: `wifi-densepose`). They continuously log the CSI tensors (52 subcarriers in HT20 mode) of passing packets and stream them as hyper-compressed `ADR-018` UDP binaries to the Phantom Scan backend.

### Stage B: Pre-Processing & Sensor Fusion
Because raw CSI phase is extremely noisy, the Phantom Node.js backend sanitizes it using:
1.  **Phase Unwrapping:** Removing artificial hardware offsets (CFO/SFO).
2.  **Kalman Filtering:** Fusing the localized arrays from the multiple ESP32 nodes into a 3D spatial centroid representing the subject's core.

### Stage C: WASM Edge Inference
Unlike heavy academic models that require massive cloud GPUs, Phantom Scan uses a specialized, pre-trained neural estimator built in Rust: the `wifi-densepose-wasm-edge` crate. 
1. The backend passes the sanitized CSI matrices into an isolated **WebAssembly (WASM)** runtime context.
2. The WASM module runs the inference algorithm in under 50 milliseconds.
3. It outputs **17 skeletal keypoints** mapped to spatial coordinates relative to the subject centroid (equivalent to standard COCO pose datasets).

### Stage D: 3D UI Rendering
The Node.js server acts as a WebSocket relay, streaming the calculated 17 keypoints to the React frontend at 20 Hz. The frontend engine (*React Three Fiber*) consumes these coordinates and binds them to the `HumanMesh.tsx` component, animating a real-time, low-poly wireframe of the target’s pose on the command dashboard.

---

## 3. Where is WiFi-DensePose Used in the Codebase?

If you are modifying or debugging the DensePose integration, refer to the following sub-systems:

| Component | File / Path | Purpose |
| :--- | :--- | :--- |
| **Firmware Config** | `firmware/esp32-csi-node/main/Kconfig.projbuild` | Defines the target SSID (`wifi-densepose`) that the hardware listens to for generating CSI. |
| **Rust WASM Crate** | `firmware/esp32-csi-node/README.md` (ref: `wifi-densepose-wasm-edge`) | The source crate for building the WebAssembly logic that transforms CSI into 17 keypoints. |
| **Edge Integration** | `firmware/esp32-csi-node/main/wasm_runtime.h` | The C-header interfacing the ESP32 hardware memory with the compiled WASM execution engine. |
| **System Architecture** | `docs/SYSTEM_DESIGN_TECHNICAL_ARCHITECTURE.md` | Maps out the "Multistatic CSI fusion → DensePose skeleton mapping" pipeline. |
| **Frontend Renderer** | `client/src/components/dashboard/HumanMesh.tsx` | The React Three Fiber component responsible for taking the 17 keypoints and rendering the 3D human wireframe mesh. |

---

## 4. Key Use Cases

By identifying *posture* rather than just presence, this integration unlocks advanced capabilities:
*   **Elderly Fall Detection:** Distinguishing whether an occlusion is "standing up" versus "lying flat on the floor" behind a bathroom door without cameras.
*   **Tactical Reconnaissance:** Determining if a hostile target behind a concrete wall is holding a weapon stance or sitting down.
*   **Hostage Rescue:** Differentiating the posture of multiple people clustered tightly in the same room.
