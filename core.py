# --- Imports ---
# os: path manipulation, directory creation, folder walking.
# shutil: copying files that can't be processed (not UTF-8) through unchanged.
import os
import shutil

# ---------- Core escape logic ----------
# This module contains no UI code (no tkinter imports) so it can be reused
# unchanged by a future Streamlit layer or any other frontend.

# Characters Java treats as whitespace between key and value.
_WS = " \t\f"

# ---------- Character groups ----------
# Every non-ASCII character belongs to exactly one group, so the UI can offer
# one checkbox per group. Order here is the order the checkboxes appear in.
# Each entry: (key, label, example text, [(first, last), ...] code point ranges).
# "other" has no ranges — it catches any non-ASCII character not listed above.
# "emoji" is code points above U+FFFF, which are written as surrogate pairs.
GROUPS = [
    ("latin1", "Latin-1 accents", "é ñ ü ß ©", [(0x0080, 0x00FF)]),
    ("latin_ext", "Other Latin (Extended)", "ł ő č ă", [(0x0100, 0x024F), (0x1E00, 0x1EFF)]),
    ("greek_cyrillic", "Greek & Cyrillic", "α β Привет", [(0x0370, 0x052F)]),
    ("hebrew_arabic", "Hebrew & Arabic", "שלום مرحبا", [(0x0590, 0x06FF), (0x0750, 0x077F)]),
    ("indic_sea", "Indic & South-East Asian", "हिन्दी ไทย", [(0x0900, 0x0DFF), (0x0E00, 0x0EFF), (0x1000, 0x109F)]),
    ("cjk", "CJK (Han, Kana, Hangul)", "東京 かな 한", [(0x3000, 0x9FFF), (0xAC00, 0xD7AF), (0xFF00, 0xFFEF)]),
    ("symbols", "Symbols & punctuation", "€ — “ ” … →", [(0x2000, 0x2BFF)]),
    ("emoji", "Emoji & supplementary", "😀 𠀀", [(0x10000, 0x10FFFF)]),
    ("other", "Everything else", "other scripts", []),
]
GROUP_KEYS = [g[0] for g in GROUPS]

def group_of(code_point):
    """Return the group key a non-ASCII code point belongs to."""
    for key, _label, _example, ranges in GROUPS:
        for first, last in ranges:
            if first <= code_point <= last:
                return key
    return "other"

def escape_non_ascii(text, groups=None):
    r"""Escape non-ASCII characters as \uXXXX (surrogate pairs above 0xFFFF).

    `groups` is the collection of group keys to escape; None means all of them.
    Characters in groups that are not selected are left as-is.
    """
    # --- escape_non_ascii ---
    # Target is Java 8, whose Properties.load(InputStream) reads ISO-8859-1.
    # Writing Latin-1 characters (é, ñ, ü) as raw UTF-8 would be misread as two
    # garbage characters each, so by default everything above ASCII is escaped
    # (this is what the JDK's native2ascii tool did). Deselecting a group
    # leaves its characters as raw UTF-8 — the caller's choice.
    #   - Code points up to 0xFFFF become \uXXXX.
    #   - Code points above 0xFFFF are split into a UTF-16 surrogate pair of two
    #     \uXXXX escapes — the only form Java understands (it has no 8-digit
    #     \UXXXXXXXX escape).
    # Existing \uXXXX sequences are pure ASCII, so they pass through untouched
    # and re-running the tool on its own output is safe.
    selected = None if groups is None else set(groups)
    escaped = []
    for char in text:
        code_point = ord(char)
        if code_point <= 0x7F:
            escaped.append(char)
        elif selected is not None and group_of(code_point) not in selected:
            escaped.append(char)
        elif code_point <= 0xFFFF:
            escaped.append(f"\\u{code_point:04x}")
        else:
            offset = code_point - 0x10000
            high = 0xD800 + (offset >> 10)
            low = 0xDC00 + (offset & 0x3FF)
            escaped.append(f"\\u{high:04x}\\u{low:04x}")
    return "".join(escaped)

def _ends_with_continuation(line):
    # A line continues onto the next one if it ends in an ODD number of
    # backslashes (an even number is just escaped backslashes).
    trailing = len(line) - len(line.rstrip("\\"))
    return trailing % 2 == 1

def _split_entry(line):
    # Splits a key/value line into (prefix, value) following Java's rules:
    # leading whitespace is skipped; the key ends at the first UNescaped
    # '=', ':' or whitespace (a backslash escapes the next character, so
    # `key\:name=value` keeps its colon in the key); the separator is optional
    # whitespace, at most one '=' or ':', then more optional whitespace.
    # prefix = everything up to the value (kept verbatim); value = the rest.
    n = len(line)
    i = 0
    while i < n and line[i] in _WS:
        i += 1
    while i < n:
        char = line[i]
        if char == "\\":
            i += 2
            continue
        if char in "=:" or char in _WS:
            break
        i += 1
    i = min(i, n)
    j = i
    while j < n and line[j] in _WS:
        j += 1
    if j < n and line[j] in "=:":
        j += 1
        while j < n and line[j] in _WS:
            j += 1
    return line[:j], line[j:]

def process_properties_line(line, continued=False, groups=None):
    """Escape the value part of one physical .properties line.

    Returns (new_line, continues) where `continues` says the NEXT physical
    line is a continuation of this logical line.
    """
    # --- process_properties_line ---
    # Cases:
    #   1. Continuation line (previous line ended in an odd number of
    #      backslashes): the whole line is value text, so all of it is escaped.
    #      Leading whitespace here is part of the line, not indentation to
    #      skip, but it's ASCII so it passes through either way.
    #   2. Blank lines and comments (# or !, after optional indentation) are
    #      returned unchanged. Comments can't continue onto the next line.
    #   3. Key/value lines: prefix (indent + key + separator) is kept as-is
    #      and only the value is escaped.
    line = line.rstrip("\n")
    if continued:
        return escape_non_ascii(line, groups), _ends_with_continuation(line)
    stripped = line.lstrip(_WS)
    if not stripped or stripped[0] in "#!":
        return line, False
    prefix, value = _split_entry(line)
    return prefix + escape_non_ascii(value, groups), _ends_with_continuation(line)

def process_file(src_path, dest_path, log_changes=False, preserve_trailing_newline=False, groups=None):
    """Process one .properties file. Returns (status, changes).

    status is "processed" or "copied" (file wasn't UTF-8, so it was copied
    to the output unchanged rather than dropped).
    """
    # --- process_file ---
    # Reads one .properties file, runs each line through
    # process_properties_line (tracking continuation state across lines), and
    # writes the result to dest_path.
    #
    # Non-UTF-8 files: can't be safely decoded, so they are copied byte-for-byte
    # to the mirrored output path. Such files (e.g. genuine ISO-8859-1) can't
    # hold characters above 0xFF anyway, so there's nothing for us to escape,
    # and copying keeps the output tree a complete mirror.
    #
    # Change tracking: when log_changes=True, any line whose escaped version
    # differs from the original is recorded as "Line N: before → after".
    #
    # Trailing newline: "\n".join(...) adds none at the end, so
    # preserve_trailing_newline=True appends one.
    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    try:
        with open(src_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        shutil.copyfile(src_path, dest_path)
        return "copied", []

    escaped_lines = []
    changes = []
    continued = False

    for idx, line in enumerate(lines, start=1):
        escaped_line, continued = process_properties_line(line, continued, groups)
        escaped_lines.append(escaped_line)
        if log_changes and escaped_line != line.rstrip("\n"):
            changes.append(f"Line {idx}: {line.rstrip()} → {escaped_line}")

    output = "\n".join(escaped_lines)
    if preserve_trailing_newline:
        output += "\n"

    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(output)

    return "processed", changes

def validate_folders(src, dest):
    """Return an error message if the folder pair is unusable, else None."""
    # The output must not be the input folder (it would overwrite the sources)
    # or inside it (the next run would walk the previous output and nest
    # another copy one level deeper each time).
    if not src or not os.path.isdir(src):
        return "Please select a valid input folder."
    if not dest:
        return "Please select an output folder."
    src_real = os.path.normcase(os.path.realpath(src))
    dest_real = os.path.normcase(os.path.realpath(dest))
    if src_real == dest_real:
        return "The output folder is the same as the input folder. Choose a different output folder so the source files aren't overwritten."
    try:
        inside = os.path.commonpath([src_real, dest_real]) == src_real
    except ValueError:  # different drives
        inside = False
    if inside:
        return "The output folder is inside the input folder. Choose an output folder outside it."
    return None

def process_folder(src_folder, dest_folder, log_callback=None, log_changes=False, preserve_trailing_newline=False, groups=None):
    """Recursively process all .properties files. Returns (processed, copied) counts."""
    # --- process_folder ---
    # Walks src_folder recursively, runs process_file on every .properties
    # file, and mirrors the relative paths into dest_folder.
    #
    # log_callback receives per-file progress messages (the UI passes
    # self.log). Files copied unchanged because they aren't UTF-8 are reported
    # through it too, so they're visible rather than silently skipped.
    #
    # changes.log: written to dest_folder only if any lines were modified.
    processed = 0
    copied = 0
    all_changes = []

    for root, _, files in os.walk(src_folder):
        for filename in files:
            if filename.lower().endswith(".properties"):
                src_path = os.path.join(root, filename)
                rel_path = os.path.relpath(src_path, src_folder)
                dest_path = os.path.join(dest_folder, rel_path)
                status, changes = process_file(
                    src_path, dest_path,
                    log_changes=log_changes,
                    preserve_trailing_newline=preserve_trailing_newline,
                    groups=groups
                )
                if status == "copied":
                    copied += 1
                    if log_callback:
                        log_callback(f"⚠️ Not UTF-8, copied unchanged: {src_path}")
                    continue
                processed += 1
                if log_callback:
                    log_callback(f"✅ Processed: {src_path}")
                    for change in changes:
                        log_callback(f"   {change}")
                if changes:
                    all_changes.append((src_path, changes))

    if all_changes:
        log_file = os.path.join(dest_folder, "changes.log")
        with open(log_file, "w", encoding="utf-8") as f:
            for file_path, changes in all_changes:
                f.write(f"File: {file_path}\n")
                for change in changes:
                    f.write(f"   {change}\n")
                f.write("\n")

    return processed, copied
