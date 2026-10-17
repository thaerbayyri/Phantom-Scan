#!/usr/bin/env python3
"""Train the per-room activity classifier from data/datasets/<room>/.

    py -3.13 scripts/train/train_activity.py --room room1 [--group-by day]

Exit codes: 0 model exported; 2 refused (data too thin or the model does not
beat the baselines on held-out recordings — nothing is written except the
report); 1 usage error. See docs/DATASET_PROTOCOL.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from phantom.activity_train import TrainingRefused, train_activity  # noqa: E402
from phantom.dataset import load_room_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--room", required=True, help="roomId used when recording")
    parser.add_argument("--data-root", default="data/datasets")
    parser.add_argument("--models-root", default="models/rooms")
    parser.add_argument(
        "--group-by",
        choices=["recording", "day"],
        default="recording",
        help="hold out whole recordings (default) or whole days (stricter, needs >= 3 days)",
    )
    parser.add_argument("--permutations", type=int, default=50)
    args = parser.parse_args()

    recordings = load_room_dataset(args.data_root, args.room)
    if not recordings:
        print(f"no recordings under {args.data_root}/{args.room} — see docs/DATASET_PROTOCOL.md", file=sys.stderr)
        return 1
    days = sorted({r.day for r in recordings if r.day})
    print(f"loaded {len(recordings)} recordings from {len(days)} day(s): {', '.join(days) or 'unknown'}")
    if args.group_by == "recording" and len(days) < 3:
        print(
            "WARNING: fewer than 3 recording days — held-out recordings from the same day share RF conditions, "
            "so the reported accuracy is optimistic.",
            file=sys.stderr,
        )

    out_dir = Path(args.models_root) / args.room
    try:
        report = train_activity(recordings, out_dir, group_by=args.group_by, n_permutations=args.permutations)
    except TrainingRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report["metrics"], indent=2))
    print("confusion matrix (rows = true, cols = predicted):")
    cm = report["confusion_matrix"]
    print("  labels:", cm["labels"])
    for label, row in zip(cm["labels"], cm["rows_true_cols_pred"]):
        print(f"  {label:>8}: {row}")
    print(f"exported {out_dir / 'activity.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
