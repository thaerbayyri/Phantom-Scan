#!/usr/bin/env python3
"""Train the per-room people-count CNN from data/datasets/<room>/.

    py -3.13 scripts/train/train_count.py --room room1

Needs recordings with at least two of the count classes {0, 1, 2+} (use the
empty / still|walking|active / two_people|three_people labels), at least 2
recordings and 40 windows per class, and >= 3 recordings overall.

Exit codes: 0 model exported; 2 refused (data too thin or the model does not
beat the majority baseline, the motion-energy tree and the shuffled-label
null on held-out recordings — only the report is written); 1 usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from phantom.activity_train import TrainingRefused  # noqa: E402
from phantom.count_train import train_count  # noqa: E402
from phantom.dataset import load_room_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--room", required=True, help="roomId used when recording")
    parser.add_argument("--data-root", default="data/datasets")
    parser.add_argument("--models-root", default="models/rooms")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--permutations", type=int, default=10)
    args = parser.parse_args()

    recordings = load_room_dataset(args.data_root, args.room)
    if not recordings:
        print(f"no recordings under {args.data_root}/{args.room} — see docs/DATASET_PROTOCOL.md", file=sys.stderr)
        return 1
    counts = sorted({r.count for r in recordings})
    print(f"loaded {len(recordings)} recordings; people counts present: {counts}")

    out_dir = Path(args.models_root) / args.room
    try:
        report = train_count(recordings, out_dir, epochs=args.epochs, n_permutations=args.permutations)
    except TrainingRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report["metrics"], indent=2))
    cm = report["confusion_matrix"]
    print("confusion matrix (rows = true count class, cols = predicted; 2 = two or more):")
    print("  classes:", cm["labels"])
    for label, row in zip(cm["labels"], cm["rows_true_cols_pred"]):
        print(f"  {label:>3}: {row}")
    print(f"exported {out_dir / 'count.safetensors'} (+ count.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
