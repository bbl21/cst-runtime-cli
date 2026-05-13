from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    scripts_root = Path(__file__).resolve().parent
    if str(scripts_root) not in sys.path:
        sys.path.insert(0, str(scripts_root))

    from cst_runtime.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
