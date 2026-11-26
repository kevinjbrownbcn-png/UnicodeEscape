# --- Imports ---
# os/sys: used to resolve a writable settings file location that works both
#         when running as a plain .py script and when frozen into a PyInstaller exe.
# json: used to persist the user's chosen theme between runs.
import json
import os
import sys

# ---------- Colour palettes ----------
# Kevin's standard dark/light UI palette (see ~/.claude/CLAUDE.md). Dark is the
# app default; every widget in gui.py is restyled from one of these two dicts
# rather than hard-coding colours inline, so the whole app can be re-skinned
# by swapping the active palette.
DARK = {
    "bg": "#0f172a",         # Core App Background — Dark Obsidian Navy
    "panel": "#1e293b",      # Component Panels & Cards — Deep Slate Gray
    "header": "#0b0f19",     # Navigation / Header Underlay — Charcoal Twilight
    "accent": "#2dd4bf",     # Primary Accent / Active Tab — Electric Teal
    "amber": "#eab308",      # Direct URL / Amber Accent — Vibrant Amber
    "purple": "#a855f7",     # Corporate / Purple Accent — Bright Amethyst Purple
    "muted": "#64748b",      # Secondary / Muted Text — Cool Muted Steel
    "border": "#30363d",     # Borders & Rule Lines — Dark Grid Charcoal
    "on_accent": "#0f172a",  # Text on accent-filled buttons — navy (~9.6:1 on the teal)
    "text": "#f8fafc",       # Main Typography — Clean Off-White
    "success": "#10b981",    # Success / Toast — Emerald Green
    "error": "#ef4444",      # Error / Alert — Crimson Coral
    "warning": "#f97316",    # Warning — Sunset Orange
}

LIGHT = {
    "bg": "#f8fafc",         # Core App Background — Clean Off-White
    "panel": "#ffffff",      # Component Panels & Cards — Pure White
    "header": "#e2e8f0",     # Navigation / Header Underlay — Pale Slate
    "accent": "#0d9488",     # Primary Accent / Active Tab — Deep Teal
    "amber": "#b45309",      # Direct URL / Amber Accent — Burnt Amber
    "purple": "#9333ea",     # Corporate / Purple Accent — Royal Amethyst Purple
    "muted": "#475569",      # Secondary / Muted Text — Slate Gray
    "border": "#cbd5e1",     # Borders & Rule Lines — Light Grid Gray
    "on_accent": "#0f172a",  # Text on accent-filled buttons — navy (~4.7:1 on the deep teal)
    "text": "#0f172a",       # Main Typography — Dark Obsidian Navy
    "success": "#16a34a",    # Success / Toast — Forest Green
    "error": "#dc2626",      # Error / Alert — Deep Red
    "warning": "#ea580c",    # Warning — Burnt Orange
}

THEMES = {"dark": DARK, "light": LIGHT}
DEFAULT_THEME = "dark"

FONT_STACK = "Segoe UI"  # Windows-native match for the site-wide font stack

# ---------- Persistence ----------
# Settings are stored as a small JSON file next to the running app (the .py
# script during development, or the .exe itself once frozen by PyInstaller),
# so the theme choice survives restarts without needing an installer or
# writing into the Windows registry.
_SETTINGS_FILENAME = "escaper_settings.json"

def app_dir():
    """Directory the running app lives in — the script's folder in dev, the exe's folder when frozen.

    Used for writable/persistent files (e.g. the settings JSON) that should
    live alongside the portable exe, not inside a temporary extraction folder.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def resource_dir():
    """Directory containing bundled read-only resources (e.g. README.md).

    A onefile PyInstaller build extracts its bundled data files into a
    temporary directory at runtime (sys._MEIPASS), not next to the exe, so
    resource lookups must use this instead of app_dir().
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_dir())
    return os.path.dirname(os.path.abspath(__file__))

def _settings_path():
    return os.path.join(app_dir(), _SETTINGS_FILENAME)

def load_settings():
    """Return the saved settings dict; {} if the file is missing, unreadable or not a JSON object."""
    try:
        with open(_settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def save_settings(**updates):
    """Merge `updates` into the saved settings so unrelated keys (theme, groups…) survive."""
    data = load_settings()
    data.update(updates)
    try:
        with open(_settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass  # Non-fatal — the app still works for this session without persistence.

def load_theme():
    """Return the last-saved theme name, defaulting to 'dark' if unset or invalid."""
    theme = load_settings().get("theme", DEFAULT_THEME)
    return theme if theme in THEMES else DEFAULT_THEME

def save_theme(theme_name):
    """Persist the chosen theme name so the next launch reopens in it."""
    save_settings(theme=theme_name)
