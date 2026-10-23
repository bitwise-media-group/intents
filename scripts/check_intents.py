# Copyright 2026 BitWise Media Group Ltd
# SPDX-License-Identifier: MIT

"""Validate every intent file against the contract in templates/intent.md and the README.

Usage: uv run python scripts/check_intents.py [directory]
"""

from __future__ import annotations

import sys
from pathlib import Path

from intentlib import INTENTS_DIR, load, validate


def main(argv: list[str]) -> int:
    directory = Path(argv[1]) if len(argv) > 1 else INTENTS_DIR
    intents = load(directory)
    errors = validate(intents)
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        print(f"{len(errors)} problem(s) in {len(intents)} intents", file=sys.stderr)
        return 1
    print(f"{len(intents)} intents ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
