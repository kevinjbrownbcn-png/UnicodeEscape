# Properties Unicode Escaper

A utility for processing Java-style `.properties` files, escaping any characters outside the Latin-1 range (`> 0x00FF`) to their `\uXXXX` Unicode escape form. Useful when a downstream toolchain requires ASCII-safe `.properties` files but your source content contains non-Latin characters (e.g. CJK, Arabic, or other Unicode scripts).

---

## Files

| File | Purpose |
|---|---|
| `escape_properties_gui.py` | Core logic + tkinter GUI |
| `escape_properties_gui.spec` | PyInstaller spec file for building a standalone `.exe` |
| `build_exe.py` | Interactive helper script to build a standalone `.exe` via PyInstaller |

---

## How It Works

### Escaping logic

Each `.properties` file is read line by line. For each line:

- Blank lines and comment lines (`#` or `!`) are passed through unchanged
- Key/value lines are split on their separator (`=`, `:`, or whitespace) — only the **value** is processed, never the key
- Within the value, any character with a code point above `0x00FF` is replaced with its `\uXXXX` escape sequence
- Existing `\uXXXX` or `\UXXXXXXXX` sequences are detected and preserved as-is, preventing double-escaping

### Output

The processed files are written to the selected output folder, mirroring the source folder structure exactly. The source files are never modified.

If any lines were changed, a `changes.log` file is written to the root of the output folder listing every modification made (file, line number, before → after). No log file is created if nothing needed escaping.

Files that cannot be read as UTF-8 are skipped and reported rather than crashing the run.

---

## GUI Usage

```bash
python escape_properties_gui.py
```

The window provides:

- **Input Folder** — the folder (scanned recursively) containing the `.properties` files to process
- **Output Folder** — where processed files are written; created automatically if it doesn't exist
- **Preserve trailing newline** — tick this if the target toolchain requires files to end with a newline character; leave unticked if it doesn't. This varies by project, so check before running
- **Run button** — processes all `.properties` files found and shows a live log of progress
- **Log panel** — displays per-file results and any individual line changes inline

---

## Building a Standalone `.exe`

**Using the spec file (recommended for consistent builds):**

```bash
pip install pyinstaller
pyinstaller escape_properties_gui.spec
```

**Using `build_exe.py` (interactive helper):**

```bash
python build_exe.py
# Enter Python script name: escape_properties_gui.py
# Is this a GUI app (no console)? (y/n): y
```

Both produce the `.exe` in the `dist/` folder.

---

## Requirements

No third-party dependencies — uses only Python's standard library (`os`, `re`, `tkinter`).

---

## Notes

- Only the **contents** of each folder are processed — the input folder itself and its structure are preserved in the output
- The escaper targets characters above Latin-1 (`0x00FF`) specifically; standard Latin accented characters (e.g. `é`, `ñ`, `ü`) are left unescaped
- Running the tool multiple times on already-escaped output is safe — existing `\uXXXX` sequences are detected and not re-escaped