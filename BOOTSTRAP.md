# Bootstrap

## Node dashboard live path
- Install: `npm install`
- Type-check: `npm run check`
- Auth and Node tests: `npm run test:dashboard-auth`
- Dev runtime: `npm run dev`
- Production build: `npm run build`
- Production start: `npm run start`

## Default operator login for current local dev flow
- Username: `thaer`
- Password: `thaer`

## Python milestone runtime
- Tests: `python -m pytest`
- Live runtime: `python -m phantom.runtime live` — **binds UDP :5005; never run it
  alongside `npm run dev` (the dashboard is the canonical :5005 owner)**
- Replay runtime: `python -m phantom.runtime replay --input <session.jsonl>`
- Note: on this machine, an explicit Python 3.13 path was used during verification.

## Firmware baseline
- Open ESP-IDF shell in `firmware/esp32-csi-node`
- Build: `idf.py build`
- Flash: `idf.py -p COM5 flash monitor`

## NVS provisioning baseline
- Generate/flash node 1 NVS from existing artifacts:
  - `nvs_node1.csv`
  - `nvs_node1.bin`
- Generate/flash node 2 NVS from existing artifacts:
  - `nvs_node2.csv`
  - `nvs_node2.bin`

## Managed component cleanup note
- If `idf.py fullclean` fails because `managed_components/` hashes changed, either:
  - move intentionally modified components into `components/`, or
  - delete the affected directories under `managed_components/` and let ESP-IDF restore them

## Verified commands in this repo on June 29, 2026
- `npm run check`: passed fully in local dev
- `npm run test:dashboard-auth`: passed fully in local dev
- `npm run build`: passed fully in local dev
- `python -m pytest`: passed fully in local dev
- Firmware build was documented here, but not re-verified in this documentation pass
