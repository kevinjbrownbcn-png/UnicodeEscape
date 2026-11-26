# Module Progress

## core.py
- Escaping logic, per-file processing, and recursive folder processing — moved out of the GUI file, no UI imports
- Fixed: characters above 0xFFFF (supplementary plane) now emit a UTF-16 surrogate pair of `\uXXXX` escapes instead of an invalid `\UXXXXXXXX` — Java's Properties parser has no support for the 8-digit form
- Review round 2 (target: Java 8, reads ISO-8859-1): `escape_non_ascii` escapes everything above 0x7F (Latin-1 included); regex replaced by a Java-rules line parser (indented lines, continuation lines, first unescaped separator, escaped separators in keys); non-UTF-8 files are copied unchanged and logged instead of dropped; `validate_folders` blocks output == input or inside input; `process_folder` now returns `(processed, copied)`

- Character groups: `GROUPS` table (9 non-overlapping groups: Latin-1, Other Latin, Greek & Cyrillic, Hebrew & Arabic, Indic & SE Asian, CJK, Symbols, Emoji, Everything else) + `group_of()`; `escape_non_ascii`, `process_properties_line`, `process_file` and `process_folder` take an optional `groups` selection (None = all)

## theme.py
- `load_settings()` / `save_settings(**updates)` — merge-style JSON settings (theme + group selection don't overwrite each other); a settings file that isn't a JSON object is now ignored instead of crashing startup
- Dark/light palettes from Kevin's standard colour scheme
- `app_dir()` — writable-file location (settings JSON), resolves next to the exe when frozen
- `resource_dir()` — bundled read-only resource location (README.md), resolves to `sys._MEIPASS` in a one-file build rather than the exe's folder
- Theme choice persisted to `escaper_settings.json`, defaults to dark
- Added `on_accent` token (navy) so Run-button text is readable on the teal accent (was hard-coded white, ~1.9:1 in dark mode)

## escape_properties_gui.py
- Rebuilt with header (title + theme toggle), body (unchanged fields/log), and standard footer (copyright left, README link right)
- Footer/body pack order fixed — the expanding body must be packed after the footer or Tkinter's `pack()` gives the footer no space
- README link opens README.md via the OS default handler; falls back to a message box if not found

- "Characters to escape" panel: a checkbox per group (3-column grid), All/None, "Remember this selection next session" (default off), warning line while any group is unticked; window is 650x720
- Run passes the selection to core and logs which groups were escaped when it isn't all of them

- Window icon set via `iconbitmap` from the bundled `assets/icon.ico` (falls back to Tk's default if missing)

## assets/
- `icon.ico` (16–256 px), `icon.png` (512 px), `make_icon.py` (regenerates both; needs Pillow). Design: navy rounded tile, teal outline, teal `\u` glyph (option A of three considered)

## launcher.py
- Thin PyInstaller entry point (`from escape_properties_gui import main`)

## build_exe.py
- Argument-driven (no more `input()` menu): `python build_exe.py <regular|onefile|onedir|debug> [--open]`, so the Build Launcher can drive it. Regular is spec-based one-file; Debug is onedir with a console + verbose bootloader
- Runs PyInstaller as `python -m PyInstaller`; sets the console title, prints a result banner (mode, output path, time) and plays a Windows sound on finish/failure; exits non-zero on failure
- CLI-mode builds pass `--specpath build` so they can never overwrite the checked-in `escape_properties_gui.spec` (this happened once during testing and was corrected)
- `--add-data` bundles README.md into every build; source path is absolute since PyInstaller resolves relative `--add-data` paths against `--specpath`, not the CWD

- Icon: `--icon assets/icon.ico` plus the .ico bundled via `--add-data` so the window can load it at run time (both CLI modes and the spec)

## escape_properties_gui.spec
- Retargeted to `launcher.py`; bundles README.md via `datas`

## build_manifest.json + tools/build_gui.py
- Generic Build Launcher (master copy: `_library/installer/build_gui.py`), configured by the manifest: name "Properties Unicode Escaper", four mode cards, one "open output folder" checkbox
- `tools/*.exe` is git-ignored; rebuild with the one-liner in the README

## Verified
- All four build modes built end-to-end with the new `build_exe.py`; each exe launches to the main window. Launcher exe opens with the right title
- Escaping: BMP chars, astral emoji (surrogate pair), comments, already-escaped values — via `core.process_folder` on a sample file
- GUI: dark/light toggle, persistence across restarts, footer rendering — via live tkinter window
- Frozen builds: Regular (one-file) and One-dir both launch and open the bundled README correctly
