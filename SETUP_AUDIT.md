> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# Setup Audit

## Dependency sources found
- Node runtime: [package.json](/D:/WIFI%20csi/phanotm/phantom%20scan/package.json)
- Python runtime: [pyproject.toml](/D:/WIFI%20csi/phanotm/phantom%20scan/pyproject.toml)
- Firmware build: [firmware/esp32-csi-node/CMakeLists.txt](/D:/WIFI%20csi/phanotm/phantom%20scan/firmware/esp32-csi-node/CMakeLists.txt), [firmware/esp32-csi-node/main/idf_component.yml](/D:/WIFI%20csi/phanotm/phantom%20scan/firmware/esp32-csi-node/main/idf_component.yml)
- Existing setup docs: [docs/WINDOWS_ESP32_SETUP.md](/D:/WIFI%20csi/phanotm/phantom%20scan/docs/WINDOWS_ESP32_SETUP.md), [docs/LOCAL_DEPLOYMENT.md](/D:/WIFI%20csi/phanotm/phantom%20scan/docs/LOCAL_DEPLOYMENT.md)

## Commands actually used during this stabilization pass
- `npm run check`
- `npm run test:dashboard-auth`
- `npm run build`
- `C:\Users\thaer\AppData\Local\Programs\Python\Python313\python.exe -m pytest`
- Note: this explicit Python 3.13 path was a machine-local verification detail, not the canonical bootstrap command.

## Missing or weak prerequisites
- `pyproject.toml` is not authoritative for the current Python milestone runtime. It only declares `pyserial`, while the repo uses `pytest`, `numpy`, and the new `phantom/` package.
- The dashboard runtime requires an operator seed file at `data/operator.json` for stable authenticated startup. A sample exists at `data/operator.example.json`.
- The Node runtime uses session auth. In production, `PHANTOM_SESSION_SECRET` must be set.
- ESP-IDF managed components may block `idf.py fullclean` if the contents of `managed_components/` were modified locally.

## Required runtime directories
- `data/`
- `data/audit/`
- `data/sessions/`
- `recordings/`

## Config and sample files present
- Present: `data/operator.example.json`
- Present: `data/operator.json`
- Present: `firmware/esp32-csi-node/nvs_node1.csv`
- Present: `firmware/esp32-csi-node/nvs_node2.csv`
- Present: `firmware/esp32-csi-node/nvs_node1.bin`
- Present: `firmware/esp32-csi-node/nvs_node2.bin`

## Config and sample gaps
- No root `.env.example` is present for the Node auth/runtime environment.
- Python package metadata has not yet been normalized to the milestone-1 authoritative runtime.

## Observed setup risks
- The repo contains both `script/` and `scripts/`; `script/` appears legacy and should not be used as the authoritative tooling path without review.
- Current generated output directories `build/`, `dist/`, and `node_modules/` are checked into the working tree context and can obscure source-of-truth during audits.
- `dist/` and `node_modules/` are generated/runtime artifacts, not meaningful setup or config inputs.
