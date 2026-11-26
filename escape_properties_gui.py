# --- Imports ---
# os/sys: used to locate README.md relative to the running app (script or exe).
# tkinter (tk): Python's built-in GUI library.
# filedialog: tkinter submodule for native OS folder picker dialogs.
# messagebox: tkinter submodule for error and completion popup dialogs.
# core: pure processing logic (no UI code), reusable by any future frontend.
# theme: colour palettes + persisted light/dark preference.
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import theme as theme_module
from core import GROUPS, GROUP_KEYS, process_folder, validate_folders

# ---------- UI ----------

class EscapeApp:
    def __init__(self, root):
        # --- EscapeApp.__init__ ---
        # Builds the entire UI layout. All widgets are created and packed here;
        # interactive elements store their values in tkinter variables (StringVar,
        # BooleanVar) that are read by the run() method when the Run button is clicked.
        #
        # Layout (top to bottom):
        #   - Header bar: app title + light/dark theme toggle
        #   - Input folder field + Browse button
        #   - Output folder field + Browse button
        #   - "Characters to escape" panel: one checkbox per character group,
        #     All/None buttons, remember-selection checkbox, Java 8 warning
        #   - Trailing newline checkbox
        #   - Run button
        #   - Log panel
        #   - Footer bar: copyright + README link
        #
        # Theme: widgets are built without colours first, then colour is applied
        # in one pass by apply_theme() so toggling the theme later just re-runs
        # that same pass rather than duplicating colour logic.
        self.root = root
        self.root.title("Properties Unicode Escaper")
        self.root.geometry("650x720")
        self.root.resizable(False, False)

        # Window/taskbar icon instead of Tk's default feather. The .ico is bundled
        # in frozen builds (resource_dir()); a missing file just keeps the default.
        try:
            self.root.iconbitmap(os.path.join(theme_module.resource_dir(), "assets", "icon.ico"))
        except tk.TclError:
            pass

        self.theme_name = theme_module.load_theme()
        self.palette = theme_module.THEMES[self.theme_name]

        # Footer is packed with side="bottom" before the expanding body: pack()
        # carves up space in the order widgets are packed, so the body's
        # fill="both"/expand=True would otherwise claim the whole remaining
        # cavity and leave nothing for a widget packed after it.
        self._build_header()
        self._build_footer()
        self._build_body()

        self.apply_theme()

    # ---------- Layout ----------

    def _build_header(self):
        self.header_frame = tk.Frame(self.root, height=48)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)

        self.title_label = tk.Label(
            self.header_frame, text="Properties Unicode Escaper",
            font=(theme_module.FONT_STACK, 12, "bold")
        )
        self.title_label.pack(side="left", padx=14)

        self.theme_button = tk.Button(
            self.header_frame, font=(theme_module.FONT_STACK, 9, "bold"),
            relief="flat", bd=0, cursor="hand2", command=self.toggle_theme
        )
        self.theme_button.pack(side="right", padx=14)

    def _build_body(self):
        self.body_frame = tk.Frame(self.root)
        self.body_frame.pack(fill="both", expand=True)

        self.input_label = tk.Label(
            self.body_frame, text="Input Folder:", font=(theme_module.FONT_STACK, 10, "bold")
        )
        self.input_label.pack(anchor="w", padx=10, pady=(10, 0))
        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(self.body_frame, textvariable=self.input_var, width=80, relief="flat")
        self.input_entry.pack(padx=10, pady=2, ipady=3)
        self.input_browse_btn = tk.Button(
            self.body_frame, text="Browse", relief="flat", bd=0, cursor="hand2", command=self.browse_input
        )
        self.input_browse_btn.pack(padx=10, pady=2)

        self.output_label = tk.Label(
            self.body_frame, text="Output Folder:", font=(theme_module.FONT_STACK, 10, "bold")
        )
        self.output_label.pack(anchor="w", padx=10, pady=(10, 0))
        self.output_var = tk.StringVar()
        self.output_entry = tk.Entry(self.body_frame, textvariable=self.output_var, width=80, relief="flat")
        self.output_entry.pack(padx=10, pady=2, ipady=3)
        self.output_browse_btn = tk.Button(
            self.body_frame, text="Browse", relief="flat", bd=0, cursor="hand2", command=self.browse_output
        )
        self.output_browse_btn.pack(padx=10, pady=2)

        self._build_groups_panel()

        # Trailing newline checkbox: tick if the target toolchain requires files
        # to end with a newline. Leave unticked if it doesn't. Defaults to off.
        self.trailing_newline_var = tk.BooleanVar(value=False)
        self.trailing_newline_check = tk.Checkbutton(
            self.body_frame,
            text="Preserve trailing newline at end of file",
            variable=self.trailing_newline_var,
            font=(theme_module.FONT_STACK, 9)
        )
        self.trailing_newline_check.pack(anchor="w", padx=10, pady=(8, 0))

        self.run_button = tk.Button(
            self.body_frame, text="Run", font=(theme_module.FONT_STACK, 10, "bold"),
            relief="flat", bd=0, cursor="hand2", command=self.run
        )
        self.run_button.pack(pady=10)

        self.log_label = tk.Label(self.body_frame, text="Log:", font=(theme_module.FONT_STACK, 10, "bold"))
        self.log_label.pack(anchor="w", padx=10, pady=(10, 0))
        self.log_box = tk.Text(
            self.body_frame, height=9, width=80, state="disabled", relief="flat", wrap="word"
        )
        self.log_box.pack(padx=10, pady=5)

    def _build_groups_panel(self):
        # One checkbox per character group (core.GROUPS), all ticked by default.
        # Starting selection: all groups, unless the user previously ticked
        # "Remember selection" — then the saved selection is restored.
        settings = theme_module.load_settings()
        remember = bool(settings.get("remember_groups", False))
        saved = settings.get("groups")
        selected = set(GROUP_KEYS)
        if remember and isinstance(saved, list):
            selected = {key for key in saved if key in GROUP_KEYS}

        self.group_vars = {key: tk.BooleanVar(value=key in selected) for key in GROUP_KEYS}
        self.remember_var = tk.BooleanVar(value=remember)

        self.groups_header = tk.Frame(self.body_frame)
        self.groups_header.pack(fill="x", padx=10, pady=(10, 0))
        self.groups_label = tk.Label(
            self.groups_header, text="Characters to escape:", font=(theme_module.FONT_STACK, 10, "bold")
        )
        self.groups_label.pack(side="left")
        self.none_btn = tk.Button(
            self.groups_header, text="None", relief="flat", bd=0, cursor="hand2",
            font=(theme_module.FONT_STACK, 8), command=lambda: self._set_all_groups(False)
        )
        self.none_btn.pack(side="right", padx=(4, 0))
        self.all_btn = tk.Button(
            self.groups_header, text="All", relief="flat", bd=0, cursor="hand2",
            font=(theme_module.FONT_STACK, 8), command=lambda: self._set_all_groups(True)
        )
        self.all_btn.pack(side="right", padx=(4, 0))

        # Checkboxes laid out in a 3-column grid, in core.GROUPS order.
        self.groups_frame = tk.Frame(self.body_frame)
        self.groups_frame.pack(fill="x", padx=10, pady=(2, 0))
        self.group_checks = []
        for index, (key, label, _example, _ranges) in enumerate(GROUPS):
            check = tk.Checkbutton(
                self.groups_frame, text=label, variable=self.group_vars[key],
                font=(theme_module.FONT_STACK, 9), anchor="w", command=self._on_groups_changed
            )
            check.grid(row=index // 3, column=index % 3, sticky="w", padx=(0, 12))
            self.group_checks.append(check)
        for column in range(3):
            self.groups_frame.grid_columnconfigure(column, weight=1, uniform="groups")

        self.remember_check = tk.Checkbutton(
            self.body_frame, text="Remember this selection next session",
            variable=self.remember_var, font=(theme_module.FONT_STACK, 9),
            command=self._on_remember_changed
        )
        self.remember_check.pack(anchor="w", padx=10, pady=(4, 0))

        # Fixed two-line height so the layout doesn't jump when a warning appears.
        self.groups_warning = tk.Label(
            self.body_frame, text="", font=(theme_module.FONT_STACK, 8),
            justify="left", anchor="nw", wraplength=620, height=2
        )
        self.groups_warning.pack(fill="x", padx=10)
        self._update_groups_warning()

    def _build_footer(self):
        # Standard footer bar: copyright/tagline on the left, a README link on
        # the right in place of the usual sibling-app nav (this is a standalone
        # tool with no other apps in the suite to link to).
        self.footer_frame = tk.Frame(self.root, height=32)
        self.footer_frame.pack(fill="x", side="bottom")
        self.footer_frame.pack_propagate(False)

        self.footer_border = tk.Frame(self.footer_frame, height=1)
        self.footer_border.pack(fill="x", side="top")

        self.copyright_label = tk.Label(
            self.footer_frame,
            text="© 2026 Properties Unicode Escaper | Unicode-safe .properties files",
            font=(theme_module.FONT_STACK, 8)
        )
        self.copyright_label.pack(side="left", padx=14)

        self.readme_link = tk.Label(
            self.footer_frame, text="README", font=(theme_module.FONT_STACK, 8, "bold"), cursor="hand2"
        )
        self.readme_link.pack(side="right", padx=14)
        self.readme_link.bind("<Button-1>", self.open_readme)

    # ---------- Theme ----------

    def toggle_theme(self):
        # Flips between dark and light, persists the choice, and restyles
        # every widget in one pass via apply_theme().
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.palette = theme_module.THEMES[self.theme_name]
        theme_module.save_theme(self.theme_name)
        self.apply_theme()

    def apply_theme(self):
        p = self.palette

        self.root.configure(bg=p["bg"])

        self.header_frame.configure(bg=p["header"])
        self.title_label.configure(bg=p["header"], fg=p["text"])
        self.theme_button.configure(
            text="☀  Light Mode" if self.theme_name == "dark" else "🌙  Dark Mode",
            bg=p["header"], fg=p["accent"],
            activebackground=p["header"], activeforeground=p["accent"]
        )

        self.body_frame.configure(bg=p["bg"])
        for label in (self.input_label, self.output_label, self.log_label):
            label.configure(bg=p["bg"], fg=p["text"])

        self.trailing_newline_check.configure(
            bg=p["bg"], fg=p["text"], selectcolor=p["panel"],
            activebackground=p["bg"], activeforeground=p["text"]
        )

        # Character-group panel
        for frame in (self.groups_header, self.groups_frame):
            frame.configure(bg=p["bg"])
        self.groups_label.configure(bg=p["bg"], fg=p["text"])
        for check in (*self.group_checks, self.remember_check):
            check.configure(
                bg=p["bg"], fg=p["text"], selectcolor=p["panel"],
                activebackground=p["bg"], activeforeground=p["text"]
            )
        for btn in (self.all_btn, self.none_btn):
            btn.configure(bg=p["panel"], fg=p["text"], activebackground=p["border"], activeforeground=p["text"])
        self.groups_warning.configure(bg=p["bg"], fg=p["warning"])

        for entry in (self.input_entry, self.output_entry):
            entry.configure(
                bg=p["panel"], fg=p["text"], insertbackground=p["text"],
                highlightthickness=1, highlightbackground=p["border"], highlightcolor=p["accent"]
            )

        for btn in (self.input_browse_btn, self.output_browse_btn):
            btn.configure(bg=p["panel"], fg=p["text"], activebackground=p["border"], activeforeground=p["text"])

        self.run_button.configure(
            bg=p["accent"], fg=p["on_accent"], activebackground=p["accent"], activeforeground=p["on_accent"]
        )

        self.log_box.configure(
            bg=p["panel"], fg=p["text"], insertbackground=p["text"],
            highlightthickness=1, highlightbackground=p["border"]
        )

        self.footer_frame.configure(bg=p["header"])
        self.footer_border.configure(bg=p["border"])
        self.copyright_label.configure(bg=p["header"], fg=p["muted"])
        self.readme_link.configure(bg=p["header"], fg=p["accent"])

    # ---------- Character groups ----------

    def selected_groups(self):
        # Keys of the ticked groups, in core.GROUPS order.
        return [key for key in GROUP_KEYS if self.group_vars[key].get()]

    def _set_all_groups(self, value):
        for var in self.group_vars.values():
            var.set(value)
        self._on_groups_changed()

    def _on_groups_changed(self):
        self._update_groups_warning()
        if self.remember_var.get():
            theme_module.save_settings(groups=self.selected_groups())

    def _on_remember_changed(self):
        # Ticking saves the current selection; unticking forgets it, so the
        # next launch starts with every group ticked again.
        if self.remember_var.get():
            theme_module.save_settings(remember_groups=True, groups=self.selected_groups())
        else:
            theme_module.save_settings(remember_groups=False, groups=None)

    def _update_groups_warning(self):
        # Unticked groups stay as raw UTF-8 in the output, which Java 8 (reading
        # .properties as ISO-8859-1) will garble — warn rather than block.
        selected = self.selected_groups()
        if not selected:
            text = "⚠ No groups selected — nothing will be escaped."
        elif len(selected) < len(GROUP_KEYS):
            text = ("⚠ Unticked groups stay as raw UTF-8 in the output. Java 8 reads "
                    ".properties files as ISO-8859-1 and will garble them.")
        else:
            text = ""
        self.groups_warning.config(text=text)

    # ---------- Actions ----------

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

    def open_readme(self, event=None):
        # Opens README.md with the OS default handler. Falls back to a message
        # box if the file isn't present. Uses resource_dir() (not app_dir())
        # since a onefile build extracts bundled data into a temp folder,
        # separate from the folder the exe itself runs from.
        readme_path = os.path.join(theme_module.resource_dir(), "README.md")
        try:
            os.startfile(readme_path)
        except OSError:
            messagebox.showinfo("README", f"README not found at:\n{readme_path}")

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
        error = validate_folders(src, dest)
        if error:
            messagebox.showerror("Error", error)
            return

        # Clear previous log output before starting a new run.
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

        groups = self.selected_groups()
        if len(groups) < len(GROUP_KEYS):
            names = [label for key, label, _e, _r in GROUPS if key in groups]
            self.log("ℹ️ Escaping only: " + (", ".join(names) if names else "(nothing)"))
        self.log(f"🔍 Scanning {src} for .properties files...\n")
        processed, copied = process_folder(
            src, dest,
            log_callback=self.log,
            log_changes=True,
            preserve_trailing_newline=self.trailing_newline_var.get(),
            groups=groups
        )
        summary = f"{processed} file(s) processed"
        if copied:
            summary += f", {copied} copied unchanged (not UTF-8)"
        self.log(f"\n✅ Done! {summary}.\nOutput written to: {dest}")
        messagebox.showinfo(
            "Complete",
            f"Processing complete.\n{summary}.\nOutput folder:\n{dest}\n\n"
            "If any lines changed, a changes.log file was written to the output folder."
        )

# ---------- Main ----------

def main():
    # Creates the root tkinter window, instantiates the app (which builds
    # all widgets in __init__), then hands control to tkinter's event loop.
    # The window stays open and responsive until the user closes it.
    root = tk.Tk()
    EscapeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
