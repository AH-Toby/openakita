#!/usr/bin/env python3
"""Verify Contract A for packaged backend resources.

Contract A requires on all platforms:
1) backend executable exists in openakita-server/
2) bundled interpreter exists in openakita-server/_internal/python*
3) bundled interpreter can run `-m pip --version`
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify bundled Python contract")
    parser.add_argument(
        "--backend-dir",
        required=True,
        help="Path to openakita-server directory",
    )
    args = parser.parse_args()

    backend_dir = Path(args.backend_dir).resolve()
    if not backend_dir.is_dir():
        print(f"[ERROR] backend dir not found: {backend_dir}")
        return 1

    exe = backend_dir / ("openakita-server.exe" if sys.platform == "win32" else "openakita-server")
    if not exe.exists():
        print(f"[ERROR] backend executable missing: {exe}")
        return 1
    print(f"[OK] backend executable: {exe}")

    internal = backend_dir / "_internal"
    if sys.platform == "win32":
        candidates = [internal / "python.exe"]
    else:
        candidates = [internal / "python3", internal / "python"]

    py = next((p for p in candidates if p.exists()), None)
    if py is None:
        print("[ERROR] bundled python missing; expected one of:")
        for c in candidates:
            print(f"  - {c}")
        return 1
    print(f"[OK] bundled python: {py}")

    try:
        result = subprocess.run(
            [str(py), "-m", "pip", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        print(f"[ERROR] failed to execute bundled python: {exc}")
        return 1

    if result.returncode != 0:
        print(f"[ERROR] bundled pip check failed (exit {result.returncode})")
        stderr = (result.stderr or "").strip()
        if stderr:
            print(stderr[:500])
        return 1
    print("[OK] bundled pip check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
