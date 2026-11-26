# Properties Unicode Escaper

A utility for processing Java-style `.properties` files, escaping any non-ASCII character (`> 0x7F`) to its `\uXXXX` Unicode escape form. Useful when a downstream toolchain (e.g. Java 8, which reads `.properties` as ISO-8859-1) requires ASCII-safe files but your source content contains accented or non-Latin characters (e.g. CJK, Arabic, or other Unicode scripts).

---

## Files

| File | Purpose |
|---|---|
| `escape_properties_gui.py` | tkinter GUI — layout, theme switcher, footer |
| `core.py` | Pure processing logic (no UI code) — reusable by any future frontend |
| `theme.py` | Dark/light colour palettes + persisted theme preference |
| `launcher.py` | Stable entry point used by PyInstaller builds |
| `assets/` | App icon: `icon.ico` (exe, window and Build Launcher icon), `icon.png` (512 px logo/favicon) and `make_icon.py` to regenerate them |
| `escape_properties_gui.spec` | PyInstaller spec file for the "Regular" (one-file) build |
| `build_exe.py` | Builds a standalone `.exe` in four modes (regular, onefile, onedir, debug) |
| `build_manifest.json` | Title, modes and options shown by the Build Launcher |
| `tools/build_gui.py` | Build Launcher: a small window to pick a build mode and run it |

---

## How It Works

### Escaping logic

The output targets **Java 8**, whose `Properties.load` reads files as ISO-8859-1 — so every non-ASCII character is escaped (like the JDK's `native2ascii`), including Latin-1 characters such as `é`. Each `.properties` file is read line by line. For each line:

- Blank lines and comment lines (`#` or `!`, optionally indented) are passed through unchanged
- Key/value lines are split following Java's rules: leading whitespace is skipped, the key ends at the first *unescaped* `=`, `:` or whitespace (so `key\:name=value` keeps its colon in the key) — only the **value** is processed, never the key
- Continuation lines (a line ending in an odd number of backslashes) are treated as value text and escaped in full
- Within the value, any character above `0x7F` is replaced with its `\uXXXX` escape sequence
- Characters beyond the Basic Multilingual Plane (code point above `0xFFFF` — e.g. some emoji or rare CJK extension ideographs) are written as a UTF-16 surrogate pair of two `\uXXXX` escapes, matching how Java's `Properties` parser represents them (it has no support for an 8-digit `\UXXXXXXXX` form)
- Existing `\uXXXX` sequences are plain ASCII, so they pass through untouched — no double-escaping

### Output

The processed files are written to the selected output folder, mirroring the source folder structure exactly. The source files are never modified.

If any lines were changed, a `changes.log` file is written to the root of the output folder listing every modification made (file, line number, before → after). No log file is created if nothing needed escaping.

Files that cannot be read as UTF-8 (e.g. genuine ISO-8859-1 files) are copied to the output unchanged and flagged in the log, so the output stays a complete mirror.

The output folder must be different from the input folder and not inside it — the app refuses to run otherwise, so source files are never overwritten and repeated runs can't nest.

---

## GUI Usage

```bash
python escape_properties_gui.py
```

The window provides:

- **Theme toggle** (top right) — switches between dark and light; the choice is saved to `escaper_settings.json` next to the running app and restored on the next launch (dark is the default)
- **Input Folder** — the folder (scanned recursively) containing the `.properties` files to process
- **Output Folder** — where processed files are written; created automatically if it doesn't exist
- **Characters to escape** — one checkbox per character group; all are ticked by default. Groups: Latin-1 accents (U+0080–U+00FF), Other Latin (Extended), Greek & Cyrillic, Hebrew & Arabic, Indic & South-East Asian, CJK (Han, Kana, Hangul, full-width forms), Symbols & punctuation, Emoji & supplementary (above U+FFFF, written as surrogate pairs), and Everything else. **All** / **None** buttons tick or clear every group. Characters in unticked groups are left as raw UTF-8, which Java 8 (reading `.properties` as ISO-8859-1) will garble, so the app shows a warning while any group is unticked
- **Remember this selection next session** — off by default; when ticked, the group selection is saved to `escaper_settings.json` and restored on the next launch. Unticking it forgets the saved selection and the next launch starts with every group ticked
- **Preserve trailing newline** — tick this if the target toolchain requires files to end with a newline character; leave unticked if it doesn't. This varies by project, so check before running
- **Run button** — processes all `.properties` files found and shows a live log of progress
- **Log panel** — displays per-file results and any individual line changes inline
- **README link** (bottom right) — opens this file in your OS default Markdown/text handler

---

## Building a Standalone `.exe`

**Using `build_exe.py` (supports four modes):**

```bash
pip install pyinstaller
python build_exe.py <regular|onefile|onedir|debug> [--open]
```

| Mode | What it produces |
|---|---|
| `regular` | `dist/escape_properties_gui.exe`, built from `escape_properties_gui.spec` (one-file, windowed) |
| `onefile` | `dist/escape_properties_gui.exe`, a single portable exe, windowed |
| `onedir` | `dist/escape_properties_gui/escape_properties_gui.exe`, a folder with the exe + dependencies, windowed (faster startup) |
| `debug` | `dist/escape_properties_gui_debug/escape_properties_gui_debug.exe`, with a console and verbose bootloader output, for troubleshooting a broken build |

`--open` opens the output folder when the build succeeds. When it finishes, the console title says "finished" or "FAILED", a summary banner is printed and Windows plays a sound. `regular` can also be run directly: `pyinstaller escape_properties_gui.spec`.

**Build Launcher.** `tools/build_gui.py` is a small window that picks the mode for you and runs the build in a console. It reads `build_manifest.json` for its title, modes and options. Rebuild its exe (git-ignored) from the project root:

```bash
python -m PyInstaller --onefile --windowed --name BuildUnicodeEscape --distpath tools --workpath %TEMP%/build-gui --specpath %TEMP%/build-gui tools/build_gui.py
```

---

## Requirements

No third-party dependencies — uses only Python's standard library (`os`, `re`, `tkinter`).

---

## Notes

- Only the **contents** of each folder are processed — the input folder itself and its structure are preserved in the output
- Everything above ASCII is escaped, including Latin accented characters (e.g. `é` → `\u00e9`), because Java 8 reads the files as ISO-8859-1
- Running the tool multiple times on already-escaped output is safe — existing `\uXXXX` sequences are ASCII and left alone
- Non-ASCII characters in keys and comments are not touched
- Deselecting a character group (see **Characters to escape**) leaves those characters unescaped in the output