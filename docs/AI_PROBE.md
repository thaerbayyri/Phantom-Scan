> **HISTORICAL (superseded):** point-in-time record. Current runtime: the TS dashboard (`npm run dev`, :5000) is the sole UDP :5005 ingest — see README.md and RUN.md.

# AI Probe

Generated: 2026-07-01T04:01:07+03:00

Probe command:

```powershell
.\.venv\Scripts\python.exe -c "import json; from phantom.ai_status import probe_ai_stack; print(json.dumps(probe_ai_stack().to_dict(), indent=2))"
```

Observed result:

```json
{
  "mode": "advisory",
  "ready": true,
  "reason": "ok",
  "model_dir": "ai model and densepose\\model",
  "embedding_shape": [
    2,
    128
  ],
  "adapters": {
    "node_1": "active",
    "node_2": "active"
  }
}
```

Session mode: deterministic authority with advisory AI available.

The adapter files `node-1.json` and `node-2.json` are active. The probe confirms `torch`/`safetensors` availability and a 128-dimensional embedding per sample. Under F1, AI remains advisory and must not originate or flip the deterministic `is_human` verdict owned by `phantom.dsp`.
