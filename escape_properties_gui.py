# --- Imports ---
# os: used for path manipulation, directory creation, and file existence checks.
# re: used for two purposes — matching existing \uXXXX escape sequences to avoid
#     double-escaping them, and parsing the key/separator/value structure of each
#     .properties line.
# tkinter (tk): Python's built-in GUI library.
# filedialog: tkinter submodule for native OS folder picker dialogs.
# messagebox: tkinter submodule for error and completion popup dialogs.
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

# ---------- Core escape logic ----------

def escape_non_latin(text):
    r"""Escape characters beyond Latin-1, preserving \uXXXX and \UXXXXXXXX sequences."""
    # --- escape_non_latin ---
    # Walks through the value string character by character. For each character:
    #   - If it looks like the start of an existing \uXXXX or \UXXXXXXXX escape
    #     sequence, the full sequence is matched and passed through unchanged.
    #     This prevents double-escaping values that are already escaped.
    #   - If the character's Unicode code point is above 0x00FF (i.e. outside
    #     the Latin-1 range), it is encoded to its \uXXXX escape form using
    #     Python's built-in unicode_escape codec.
    #   - All other characters (ASCII and Latin-1 accented characters) are kept as-is.
    escaped = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in ("u", "U"):
            # Attempt to match a full existing escape sequence at this position.
            # If matched, append it verbatim and skip past it entirely.
            match = re.match(r"\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}", text[i:])
            if match:
                escaped.append(match.group(0))
                i += len(match.group(0))
                continue
        char = text[i]
        if ord(char) > 0x00FF:  # Beyond Latin-1
            escaped.append(char.encode("unicode_escape").decode("ascii"))
        else:
            escaped.append(char)
        i += 1
    return "".join(escaped)

def process_properties_line(line):
    """Escape only the value part of a .properties line."""
    # --- process_properties_line ---
    # Handles a single line from a .properties file. Three cases:
    #   1. Blank lines and comment lines (starting with # or !) are returned
    #      unchanged — they have no value to escape.
    #   2. Key/value lines are split into three groups using a regex:
    #        Group 1 (key):   everything before the separator
    #        Group 2 (sep):   the separator itself (=, :, or surrounding whitespace)
    #        Group 3 (value): everything after the separator
    #      Only the value is passed to escape_non_latin; the key and separator
    #      are reassembled unchanged.
    #   3. Lines that don't match the regex (e.g. malformed lines) are returned as-is.
    #
    # Note on the regex separator character class [:=\s]+:
    #   Matches one or more of: colon, equals sign, or whitespace. This covers
    #   all standard .properties separator styles (key=value, key = value, key: value).
    line = line.rstrip("\n")
    if not line.strip() or line.strip().startswith(("#", "!")):
        return line
    match = re.match(r'([^:=\s][^:=]*)([:=\s]+)(.*)', line)
    if match:
        key, sep, value = match.groups()
        escaped_value = escape_non_latin(value)
        return f"{key}{sep}{escaped_value}"
    return line

def process_file(src_path, dest_path, log_changes=False, preserve_trailing_newline=False):
    """Process a single .properties file and optionally log changes."""
    # --- process_file ---
    # Reads a single .properties file, processes each line through
    # process_properties_line, and writes the result to dest_path.
    #
    # UTF-8 decoding: if the file can't be read as UTF-8, it is skipped
    # entirely and reported rather than crashing — useful when a folder
    # contains mixed-encoding files.
    #
    # Change tracking: when log_changes=True, any line whose escaped version
    # differs from the original is recorded as "Line N: before → after".
    # These are returned to process_folder for writing to changes.log.
    #
    # Output directory: os.makedirs is only called when dest_path has a
    # directory component — calling it with an empty string would raise
    # FileNotFoundError for files sitting directly in the destination folder.
    #
    # Trailing newline: "\n".join(...) does not add a newline at the end of
    # the file. If preserve_trailing_newline=True (set via the UI checkbox),
    # one is appended. Leave unticked if the target toolchain is strict about
    # not having a trailing newline.
    try:
        with open(src_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        print(f"⚠️ Skipped (not UTF-8): {src_path}")
        return False, []

    escaped_lines = []
    changes = []

    for idx, line in enumerate(lines, start=1):
        escaped_line = process_properties_line(line)
        escaped_lines.append(escaped_line)
        if log_changes and escaped_line != line.rstrip("\n"):
            changes.append(f"Line {idx}: {line.rstrip()} → {escaped_line}")

    dest_dir = os.path.dirname(dest_path)
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)

    output = "\n".join(escaped_lines)
    if preserve_trailing_newline:
        output += "\n"

    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(output)

    return True, changes

def process_folder(src_folder, dest_folder, log_callback=None, log_changes=False, preserve_trailing_newline=False):
    """Recursively process all .properties files and log changes if requested."""
    # --- process_folder ---
    # Walks src_folder recursively via os.walk, finds every .properties file,
    # and calls process_file for each one. The relative path of each file is
    # preserved so the output folder mirrors the source folder structure exactly.
    #
    # log_callback is an optional function the caller provides to receive
    # per-file progress messages — the UI passes self.log so output appears
    # in the on-screen log panel in real time.
    #
    # changes.log: if any lines were modified across the run, a single
    # changes.log file is written to the root of dest_folder summarising
    # every change made. It is only created if there were actual changes —
    # a clean run (nothing needed escaping) produces no log file.
    count = 0
    all_changes = []

    for root, _, files in os.walk(src_folder):
        for filename in files:
            if filename.lower().endswith(".properties"):
                src_path = os.path.join(root, filename)
                rel_path = os.path.relpath(src_path, src_folder)
                dest_path = os.path.join(dest_folder, rel_path)
                success, changes = process_file(
                    src_path, dest_path,
                    log_changes=log_changes,
                    preserve_trailing_newline=preserve_trailing_newline
                )
                if success:
                    count += 1
                    if log_callback:
                        log_callback(f"✅ Processed: {src_path}")
                        for change in changes:
                            log_callback(f"   {change}")
                    if changes:
                        all_changes.append((src_path, changes))

    # Write a full changes.log in the output folder
    if all_changes:
        log_file = os.path.join(dest_folder, "changes.log")
        with open(log_file, "w", encoding="utf-8") as f:
            for file_path, changes in all_changes:
                f.write(f"File: {file_path}\n")
                for change in changes:
                    f.write(f"   {change}\n")
                f.write("\n")

    return count

# ---------- UI ----------

class EscapeApp:
    def __init__(self, root):
        # --- EscapeApp.__init__ ---
        # Builds the entire UI layout. All widgets are created and packed here;
        # interactive elements store their values in tkinter variables (StringVar,
        # BooleanVar) that are read by the run() method when the Run button is clicked.
        #
        # Layout (top to bottom):
        #   - Input folder field + Browse button
        #   - Output folder field + Browse button
        #   - Trailing newline checkbox
        #   - Run button
        #   - Scrollable log panel
        #
        # The log panel (tk.Text) is kept in state="disabled" at rest to prevent
        # the user from typing into it. It is briefly set to "normal" by the log()
        # method to insert new lines, then immediately disabled again.
        self.root = root
        self.root.title("Properties Unicode Escaper")
        self.root.geometry("650x490")
        self.root.resizable(False, False)

        tk.Label(root, text="Input Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.input_var = tk.StringVar()
        tk.Entry(root, textvariable=self.input_var, width=80).pack(padx=10, pady=2)
        tk.Button(root, text="Browse", command=self.browse_input).pack(padx=10, pady=2)

        tk.Label(root, text="Output Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.output_var = tk.StringVar()
        tk.Entry(root, textvariable=self.output_var, width=80).pack(padx=10, pady=2)
        tk.Button(root, text="Browse", command=self.browse_output).pack(padx=10, pady=2)

        # Trailing newline checkbox: tick if the target toolchain requires files
        # to end with a newline. Leave unticked if it doesn't. Defaults to off.
        self.trailing_newline_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            root,
            text="Preserve trailing newline at end of file",
            variable=self.trailing_newline_var
        ).pack(anchor="w", padx=10, pady=(8, 0))

        tk.Button(root, text="Run", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", command=self.run).pack(pady=10)

        tk.Label(root, text="Log:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.log_box = tk.Text(root, height=15, width=80, state="disabled", bg="#f9f9f9")
        self.log_box.pack(padx=10, pady=5)

    def browse_input(self):
        # Opens a native OS folder picker. If the user selects a folder
        # (i.e. doesn't cancel), updates the input field with the chosen path.
        path = filedialog.askdirectory(title="Select Input Folder")
        if path:
            self.input_var.set(path)

    def browse_output(self):
        # Opens a native OS folder picker for the output destination.
        # The output folder does not need to exist — process_file creates
        # it (and any subdirectories) automatically when writing files.
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_var.set(path)

    def log(self, message):
        # Appends a message to the log panel. The widget must be temporarily
        # set to "normal" to allow text insertion, then immediately returned
        # to "disabled" so the user cannot edit it. log_box.see("end") scrolls
        # to the bottom after each insert so the latest entry is always visible.
        self.log_box.config(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def run(self):
        # --- run ---
        # Called when the Run button is clicked. Validates both path fields
        # before proceeding — src must be an existing directory; dest just
        # needs to be non-empty (it will be created if it doesn't exist).
        # Clears the log panel before each run so previous output doesn't
        # accumulate across multiple runs in the same session.
        # Passes the trailing newline checkbox state through to process_folder
        # so it applies to every file in the run.
        src = self.input_var.get().strip()
        dest = self.output_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("Error", "Please select a valid input folder.")
            return
        if not dest:
            messagebox.showerror("Error", "Please select an output folder.")
            return

        # Clear previous log output before starting a new run.
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

        self.log(f"🔍 Scanning {src} for .properties files...\n")
        count = process_folder(
            src, dest,
            log_callback=self.log,
            log_changes=True,
            preserve_trailing_newline=self.trailing_newline_var.get()
        )
        self.log(f"\n✅ Done! {count} file(s) processed.\nOutput written to: {dest}")
        messagebox.showinfo("Complete", f"Processing complete.\n{count} file(s) written to:\n{dest}\n\nA changes.log file has been created in the output folder.")

# ---------- Main ----------

if __name__ == "__main__":
    # Creates the root tkinter window, instantiates the app (which builds
    # all widgets in __init__), then hands control to tkinter's event loop.
    # The window stays open and responsive until the user closes it.
    root = tk.Tk()
    app = EscapeApp(root)
    root.mainloop()
