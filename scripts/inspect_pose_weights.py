#!/usr/bin/env python3
"""
Diagnostic: inspect the actual tensor shapes inside pose_v1.safetensors and
print the matching PoseNet definition. Run this whenever the pose weights are
swapped to confirm the model architecture in ai_inference.py still matches.

    .venv\\Scripts\\python scripts/inspect_pose_weights.py
"""
import os
import sys

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ai model and densepose", "model",
)
POSE = os.path.join(MODEL_DIR, "pose_v1.safetensors")


def main():
    if not os.path.exists(POSE):
        print(f"[ERR] not found: {POSE}")
        return 1

    # Read the safetensors header directly so this works even without torch.
    import struct
    import json

    with open(POSE, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        header = json.loads(f.read(n))

    n_tensors = len(header) - (1 if "__metadata__" in header else 0)
    print(f"pose_v1.safetensors — {n_tensors} tensors\n")
    shapes = {}
    for k, v in header.items():
        if k == "__metadata__":
            print(f"__metadata__: {v}")
            continue
        shapes[k] = v["shape"]
        print(f"  {k:24s} {v['dtype']:4s} {v['shape']}")

    # Derive the architecture from the conv/fc weight shapes.
    print("\nDerived architecture:")
    try:
        c1 = shapes["enc.c1.weight"]  # [out, in, k]
        c2 = shapes["enc.c2.weight"]
        c3 = shapes["enc.c3.weight"]
        fc1 = shapes["head.fc1.weight"]  # [out, in]
        fc2 = shapes["head.fc2.weight"]
        print(f"  Conv1d({c1[1]}, {c1[0]}, kernel_size={c1[2]})")
        print(f"  Conv1d({c2[1]}, {c2[0]}, kernel_size={c2[2]})")
        print(f"  Conv1d({c3[1]}, {c3[0]}, kernel_size={c3[2]})")
        print(f"  -> global avg pool over time -> [{c3[0]}]")
        print(f"  Linear({fc1[1]}, {fc1[0]})")
        print(f"  Linear({fc2[1]}, {fc2[0]})   # {fc2[0] // 2} keypoints x 2")
    except KeyError as e:
        print(f"  (could not derive — missing key {e})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
