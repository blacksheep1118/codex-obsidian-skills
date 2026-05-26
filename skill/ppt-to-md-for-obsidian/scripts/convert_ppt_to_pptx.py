#!/usr/bin/env python3
"""Convert legacy .ppt files to .pptx with LibreOffice.

The script is a thin wrapper around LibreOffice/soffice. It does not modify the
source file and writes converted files to an output directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


MACOS_SOFFICE = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
WINDOWS_SOFFICE_PATHS = (
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
)


def soffice_candidates(explicit: str | None = None) -> list[str]:
    candidates = []
    if explicit:
        candidates.append(explicit)
    candidates.extend(["soffice", "soffice.exe", "libreoffice", "libreoffice.exe"])
    candidates.append(str(MACOS_SOFFICE))
    candidates.extend(str(path) for path in WINDOWS_SOFFICE_PATHS)
    return candidates


def find_soffice(explicit: str | None = None) -> str:
    for candidate in soffice_candidates(explicit):
        direct = Path(candidate).expanduser()
        if direct.exists():
            return str(direct)
        found = shutil.which(candidate)
        if found:
            return found

    raise SystemExit(
        "LibreOffice was not found. Install LibreOffice or pass --soffice "
        "with the path to the soffice executable. On Windows this is often "
        r"C:\Program Files\LibreOffice\program\soffice.exe."
    )


def convert_one(path: Path, out_dir: Path, soffice: str) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".ppt":
        raise ValueError(f"expected a .ppt file, got: {path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    before = set(out_dir.glob("*.pptx"))

    cmd = [
        soffice,
        "--headless",
        "--convert-to",
        "pptx",
        "--outdir",
        str(out_dir),
        str(path),
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            "LibreOffice conversion failed\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    expected = out_dir / f"{path.stem}.pptx"
    if expected.exists():
        return expected

    after = set(out_dir.glob("*.pptx"))
    created = sorted(after - before)
    if created:
        return created[0]

    raise RuntimeError(
        "LibreOffice finished without producing a .pptx file. "
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def iter_inputs(input_path: Path) -> list[Path]:
    if input_path.is_dir():
        return sorted(input_path.glob("*.ppt"))
    return [input_path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert .ppt files to .pptx.")
    parser.add_argument("input", type=Path, help="A .ppt file or directory")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("converted_pptx"),
        help="Directory for converted .pptx files",
    )
    parser.add_argument("--soffice", help="Path to LibreOffice soffice binary")
    args = parser.parse_args()

    soffice = find_soffice(args.soffice)
    inputs = iter_inputs(args.input)
    if not inputs:
        parser.error(f"no .ppt files found in {args.input}")

    for path in inputs:
        converted = convert_one(path, args.out_dir, soffice)
        print(converted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
