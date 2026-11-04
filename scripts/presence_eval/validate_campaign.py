"""CLI entry point: ``python -m scripts.presence_eval.validate_campaign <campaign folder>`` (see campaign.py for the rules)."""
from __future__ import annotations

import sys

from .campaign import main

if __name__ == "__main__":
    sys.exit(main())
