"""PyInstaller entry point.

Kept separate from escape_properties_gui.py so the build always targets a
single, stable file regardless of how the app's internals are split across
modules (core.py, theme.py, escape_properties_gui.py). Running this directly
is equivalent to running escape_properties_gui.py.
"""
from escape_properties_gui import main

if __name__ == "__main__":
    main()
