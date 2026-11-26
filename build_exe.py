#!/usr/bin/env python3
"""Build the Properties Unicode Escaper Windows executable with PyInstaller.

Four modes, all built from launcher.py (the stable entry point, see launcher.py):

  regular  built from escape_properties_gui.spec (one-file, windowed)
             dist/escape_properties_gui.exe
  onefile  single portable exe, no console
             dist/escape_properties_gui.exe
  onedir   folder with the exe and its dependencies, no console (faster startup)
             dist/escape_properties_gui/escape_properties_gui.exe
  debug    onedir with a console window and verbose bootloader output
             dist/escape_properties_gui_debug/escape_properties_gui_debug.exe

Usage:
  python build_exe.py <mode> [--open]

--open opens the output folder when the build succeeds.
Requires PyInstaller (pip install pyinstaller).

The console title shows "running" while it works; a banner at the end gives the result, the time
taken and the file produced, and Windows plays its notification sound (a different one on
failure). The Build Launcher in tools/ runs this script, so those signals show there too.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_NAME = "escape_properties_gui"  # exe name; the display name lives in build_manifest.json
ENTRY_POINT = "launcher.py"
SPEC_FILE = "escape_properties_gui.spec"
# Absolute path: PyInstaller resolves --add-data source paths relative to --specpath (not the
# CWD) once --specpath is given, so a relative "README.md" would otherwise be looked up inside
# build/ instead of the project root.
README_PATH = ROOT / "README.md"
# The exe's icon (--icon) and a copy bundled as data so the window can use it at run time.
ICON_PATH = ROOT / "assets" / "icon.ico"
MODES = ("regular", "onefile", "onedir", "debug")


class BuildFailed(Exception):
    """A build step exited with an error (or a required tool is missing)."""


# ---------------------------------------------------------------- "is it done yet?" signals
def set_title(state: str) -> None:
    """Console window title, so the state is visible from the taskbar (Windows only)."""
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleTitleW(f"Unicode Escaper build: {state}")
        except (AttributeError, OSError):
            pass


def notify(ok: bool) -> None:
    """Windows' notification sound on success, its error sound on failure. Never fails."""
    if os.name == "nt":
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_OK if ok else winsound.MB_ICONHAND)
        except (ImportError, RuntimeError):
            pass


def elapsed(started: float) -> str:
    seconds = int(time.monotonic() - started)
    return f"{seconds // 60} min {seconds % 60:02d} s" if seconds >= 60 else f"{seconds} s"


def banner(lines: list[str], ok: bool) -> None:
    rule = ("=" if ok else "!") * 64
    print(f"\n{rule}")
    for line in lines:
        print(f"  {line}")
    print(rule, flush=True)


# ------------------------------------------------------------------------------- building
def check_pyinstaller() -> None:
    """Fail early with a clear message if PyInstaller isn't installed."""
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        raise BuildFailed("PyInstaller isn't installed. Install it with: pip install pyinstaller")


def pyinstaller_command(mode: str) -> list[str]:
    """The PyInstaller command line for a mode.

    `regular` uses the checked-in spec. The other modes build from the entry point with flags;
    --specpath sends their auto-generated .spec into build/ so it can never collide with (and
    silently overwrite) the hand-maintained escape_properties_gui.spec used by `regular`.
    """
    base = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean"]
    if mode == "regular":
        return [*base, SPEC_FILE]

    name = f"{APP_NAME}_debug" if mode == "debug" else APP_NAME
    cmd = [*base, "--name", name, "--distpath", "dist", "--workpath", f"build/{mode}",
           "--specpath", "build", "--add-data", f"{README_PATH};.",
           "--add-data", f"{ICON_PATH};assets", "--icon", str(ICON_PATH)]
    if mode == "onefile":
        cmd += ["--onefile", "--windowed"]
    elif mode == "onedir":
        cmd += ["--onedir", "--windowed"]
    else:  # debug: console visible so tracebacks can be read, plus PyInstaller's boot logging
        cmd += ["--onedir", "--console", "--debug=all"]
    # With --specpath set, relative entry-point paths resolve against it, so pass an absolute one.
    return [*cmd, str(ROOT / ENTRY_POINT)]


def expected_output(mode: str) -> Path:
    """What each mode produces (see the table in the module docstring)."""
    dist = ROOT / "dist"
    return {
        "regular": dist / f"{APP_NAME}.exe",
        "onefile": dist / f"{APP_NAME}.exe",
        "onedir": dist / APP_NAME / f"{APP_NAME}.exe",
        "debug": dist / f"{APP_NAME}_debug" / f"{APP_NAME}_debug.exe",
    }[mode]


def run(cmd: list[str]) -> None:
    """Run a command from the project root, streaming output; raise BuildFailed on failure."""
    print(f"\n> {' '.join(cmd)}", flush=True)
    set_title("running: PyInstaller")
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        raise BuildFailed("PyInstaller reported an error (see the output above).")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        epilog=__doc__.split("\n\n", 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode", choices=MODES, help="build mode")
    parser.add_argument("--open", action="store_true", help="open the output folder when the build succeeds")
    args = parser.parse_args()

    started = time.monotonic()
    set_title("starting")
    try:
        check_pyinstaller()
        run(pyinstaller_command(args.mode))
        output = expected_output(args.mode)
        if not output.exists():
            raise BuildFailed(f"Build finished but {output} was not produced.")
    except BuildFailed as exc:
        set_title(f"{args.mode} FAILED")
        notify(False)
        banner([f"BUILD FAILED: {args.mode}", str(exc), f"Time: {elapsed(started)}"], ok=False)
        return 1

    set_title(f"{args.mode} finished")
    notify(True)
    banner([f"BUILD FINISHED: {args.mode}", f"Output: {output}", f"Time: {elapsed(started)}"], ok=True)
    if args.open and os.name == "nt":
        os.startfile(output.parent)  # noqa: S606 (Windows-only by design)
    return 0


if __name__ == "__main__":
    sys.exit(main())
