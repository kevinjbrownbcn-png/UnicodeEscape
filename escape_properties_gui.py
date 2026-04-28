import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox

# ---------- Core escape logic ----------

def escape_non_latin(text):
    r"""Escape characters beyond Latin-1, preserving \uXXXX and \UXXXXXXXX sequences."""
    escaped = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in ("u", "U"):
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
    line = line.rstrip("\n")
    if not line.strip() or line.strip().startswith(("#", "!")):
        return line
    match = re.match(r'([^:=\s][^:=]*)([:=|\s]+)(.*)', line)
    if match:
        key, sep, value = match.groups()
        escaped_value = escape_non_latin(value)
        return f"{key}{sep}{escaped_value}"
    return line

def process_file(src_path, dest_path, log_changes=False):
    """Process a single .properties file and optionally log changes."""
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

    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(escaped_lines))

    return True, changes

def process_folder(src_folder, dest_folder, log_callback=None, log_changes=False):
    """Recursively process all .properties files and log changes if requested."""
    count = 0
    all_changes = []

    for root, _, files in os.walk(src_folder):
        for filename in files:
            if filename.lower().endswith(".properties"):
                src_path = os.path.join(root, filename)
                rel_path = os.path.relpath(src_path, src_folder)
                dest_path = os.path.join(dest_folder, rel_path)
                success, changes = process_file(src_path, dest_path, log_changes=log_changes)
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
        self.root = root
        self.root.title("Properties Unicode Escaper")
        self.root.geometry("650x450")
        self.root.resizable(False, False)

        tk.Label(root, text="Input Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.input_var = tk.StringVar()
        tk.Entry(root, textvariable=self.input_var, width=80).pack(padx=10, pady=2)
        tk.Button(root, text="Browse", command=self.browse_input).pack(padx=10, pady=2)

        tk.Label(root, text="Output Folder:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.output_var = tk.StringVar()
        tk.Entry(root, textvariable=self.output_var, width=80).pack(padx=10, pady=2)
        tk.Button(root, text="Browse", command=self.browse_output).pack(padx=10, pady=2)

        tk.Button(root, text="Run", font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white", command=self.run).pack(pady=10)

        tk.Label(root, text="Log:", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.log_box = tk.Text(root, height=15, width=80, state="disabled", bg="#f9f9f9")
        self.log_box.pack(padx=10, pady=5)

    def browse_input(self):
        path = filedialog.askdirectory(title="Select Input Folder")
        if path:
            self.input_var.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self.output_var.set(path)

    def log(self, message):
        self.log_box.config(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    def run(self):
        src = self.input_var.get().strip()
        dest = self.output_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("Error", "Please select a valid input folder.")
            return
        if not dest:
            messagebox.showerror("Error", "Please select an output folder.")
            return

        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

        self.log(f"🔍 Scanning {src} for .properties files...\n")
        count = process_folder(src, dest, log_callback=self.log, log_changes=True)
        self.log(f"\n✅ Done! {count} file(s) processed.\nOutput written to: {dest}")
        messagebox.showinfo("Complete", f"Processing complete.\n{count} file(s) written to:\n{dest}\n\nA changes.log file has been created in the output folder.")

# ---------- Main ----------

if __name__ == "__main__":
    root = tk.Tk()
    app = EscapeApp(root)
    root.mainloop()
