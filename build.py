"""Build the chord switcher executable with Flet and PyInstaller: python build.py"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = Path("src")
NAME = "ChordSwitcher"


def main():
    for module in ("flet_cli", "flet_desktop", "PyInstaller", "PIL"):
        if importlib.util.find_spec(module) is None:
            sys.exit(f"{module} is missing. Run: \"{sys.executable}\" -m pip install "
                     f"-r \"{ROOT / 'requirements.txt'}\" \"flet[cli]\" pyinstaller")

    result = subprocess.run(
        [sys.executable, "-m", "flet_cli.cli", "pack", str(SRC / "chord_loop.py"), "--name", NAME, "--yes",
         "--add-data", f"{SRC / 'assets'}{os.pathsep}assets"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    name = f"{NAME}.exe" if sys.platform == "win32" else NAME
    print(f"Built {ROOT / 'dist' / name}")


if __name__ == "__main__":
    main()
