"""Generic Build Launcher.

A small picker for a project's build modes. Choose a mode, tick any options, press Run, and it
opens a console window running the project's build script so the output is visible and stays
visible (`cmd /k`): the point of this tool is to save typing, not to hide the build.

One copy of this file lives in every project's tools/ folder (master copy: _library/installer),
so a fresh clone can always rebuild the launcher. Nothing here is project-specific: the title,
footer, build modes and checkboxes all come from `build_manifest.json` in the project root (see
below). With no manifest it still works in a reduced form: the project folder's name, and a
single "Run" for build_exe.py (or build.py).

Tkinter rather than a web UI: it's in the standard library, so the packaged .exe needs no
bundled runtime and stays small.

build_manifest.json (all keys optional):
  {
    "name": "LinkSift",                    title bar, header and footer
    "glyph": "🔗",                         emoji before the header name
    "subtitle": "Pick a build mode...",    line under the header
    "footer": "© {year} LinkSift | Build Launcher",   footer text ({year}, {name} expand)
    "script": "build_exe.py",              what to run, relative to the project root
    "icon": "resources/icon.ico",          window icon, relative to the project root
    "readme": "README.md",                 opened by the footer link, relative to the root
    "note": "Output goes to dist/. ...",   caption above the buttons
    "modes": [                             radio cards; only what's listed is shown
      {"label": "Installer", "desc": "Setup .exe ...", "args": ["regular"]}
    ],
    "options": [                           checkboxes
      {"id": "checks", "label": "Run checks first", "default": true,
       "args_on": [], "args_off": ["--skip-checks"]}
    ]
  }

  One mode:  shown as a single card, nothing to choose. No modes: no cards, just the options.

Build it with (from the project root, so --specpath-relative paths stay simple):
  python -m PyInstaller --onefile --windowed --name Build<Name> --icon resources/icon.ico ^
      --distpath tools --workpath %TEMP%/build-gui --specpath %TEMP%/build-gui tools/build_gui.py

(--icon needs an absolute path when --specpath points elsewhere. The window icon at runtime
comes from the manifest's "icon", so nothing needs bundling with --add-data.)

Command line:
  build_gui.py [project_root]            open the launcher (root is found automatically if omitted)
  build_gui.py --dry-run [project_root]  print what would be shown and run, without a window
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys

try:  # Tk is only needed for the window; --dry-run works without it
    import tkinter as tk
    from tkinter import messagebox
except ImportError:  # pragma: no cover
    tk = None

MANIFEST = "build_manifest.json"
DEFAULT_SCRIPTS = ("build_exe.py", "build.py")  # tried in order when the manifest names none
DEFAULT_NOTE = "The build runs in a console window that stays open when it's done."
FOOTER_TAGLINE = "Build Launcher"

# Kevin's standard palette, with the WCAG AA text shades used for small text
# (muted captions in dark, teal in light). Dark is the default; the choice is remembered.
THEMES = {
    "dark": {
        "bg": "#0f172a", "panel": "#1e293b", "nav": "#0b0f19", "border": "#30363d",
        "accent": "#2dd4bf", "accent_fill": "#2dd4bf", "on_accent": "#0f172a",
        "text": "#f8fafc", "muted": "#8b9ab0", "error": "#f87171",
        "select": "#1e293b", "hover": "#334155",
    },
    "light": {
        "bg": "#f8fafc", "panel": "#ffffff", "nav": "#e2e8f0", "border": "#cbd5e1",
        "accent": "#0e7168", "accent_fill": "#0e7168", "on_accent": "#ffffff",
        "text": "#0f172a", "muted": "#475569", "error": "#dc2626",
        "select": "#ffffff", "hover": "#e2e8f0",
    },
}

FONT = "Segoe UI"


# ------------------------------------------------------------------ project + manifest
def launcher_dir():
    """Folder the launcher runs from (the .exe's folder once frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_project_root(explicit=None):
    """The project folder: the one holding build_manifest.json or the build script.

    An explicit folder (command-line argument) wins. Otherwise checked in order: beside the
    launcher, one level up (the normal case: tools/Build<Name>.exe), then the working
    directory. Returns None if nothing matches, which the caller reports rather than guessing.
    """
    if explicit:
        return os.path.abspath(explicit) if os.path.isdir(explicit) else None
    here = launcher_dir()
    for candidate in (here, os.path.dirname(here), os.getcwd()):
        if os.path.isfile(os.path.join(candidate, MANIFEST)):
            return candidate
        if any(os.path.isfile(os.path.join(candidate, s)) for s in DEFAULT_SCRIPTS):
            return candidate
    return None


def _str_list(value):
    """A manifest `args` value as a clean list of strings (anything else becomes empty)."""
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def load_config(root):
    """The manifest merged over defaults, with every field validated.

    A missing or corrupt manifest isn't an error: the launcher falls back to the folder name
    and a single card, and `warning` says why so the window can show it.
    """
    raw, warning = {}, None
    manifest_path = os.path.join(root, MANIFEST)
    if os.path.isfile(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                raw = loaded
            else:
                warning = f"{MANIFEST} should hold a JSON object; using defaults."
        except (OSError, ValueError) as exc:
            warning = f"Could not read {MANIFEST} ({exc}); using defaults."

    name = str(raw.get("name") or os.path.basename(root.rstrip("\\/")) or "Project")
    script = str(raw.get("script") or next(
        (s for s in DEFAULT_SCRIPTS if os.path.isfile(os.path.join(root, s))), DEFAULT_SCRIPTS[0]))

    modes = []
    for item in raw.get("modes") or []:
        if isinstance(item, dict) and item.get("label"):
            modes.append({"label": str(item["label"]), "desc": str(item.get("desc") or ""),
                          "args": _str_list(item.get("args"))})
    # No manifest modes and no manifest at all: a single card so there's still something to run.
    if not modes and not raw:
        modes.append({"label": "Build", "desc": f"Runs {script}", "args": []})

    options = []
    for index, item in enumerate(raw.get("options") or []):
        if isinstance(item, dict) and item.get("label"):
            options.append({"id": str(item.get("id") or f"opt{index}"), "label": str(item["label"]),
                            "default": bool(item.get("default", False)),
                            "args_on": _str_list(item.get("args_on")),
                            "args_off": _str_list(item.get("args_off"))})

    year = datetime.date.today().year
    footer = str(raw.get("footer") or f"© {{year}} {{name}} | {FOOTER_TAGLINE}")
    return {
        "root": root,
        "name": name,
        "glyph": str(raw.get("glyph") or ""),
        "title": f"{name} — Build Launcher",
        "subtitle": str(raw.get("subtitle") or "Pick a build mode and run it in a console"),
        "footer": footer.replace("{year}", str(year)).replace("{name}", name),
        "script": script,
        "icon": str(raw.get("icon") or ""),
        "readme": str(raw.get("readme") or "README.md"),
        "note": str(raw.get("note") or DEFAULT_NOTE),
        "modes": modes,
        "options": options,
        "warning": warning,
    }


def slug(text):
    """A filename-safe form of the project name, for the per-project preferences file."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "project"


def cmd_safe(text):
    """Text that can sit in a cmd `title` command: strips the characters cmd would act on."""
    return re.sub(r'[&|<>^()%"!]', "", text)


# ------------------------------------------------------------------------- preferences
def settings_path(name):
    """Where the remembered theme and options live.

    Under LOCALAPPDATA rather than next to the .exe, so the preference still saves if the
    launcher is dropped somewhere read-only, and so it never dirties the repo. One file per
    project, since every project carries its own copy of this launcher.
    """
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "BuildLauncher")
    try:
        os.makedirs(folder, exist_ok=True)
        return os.path.join(folder, f"{slug(name)}.json")
    except OSError:
        return None


def load_prefs(name, options):
    prefs = {"theme": "dark", "options": {o["id"]: o["default"] for o in options}}
    path = settings_path(name)
    if path and os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if stored.get("theme") in THEMES:
                prefs["theme"] = stored["theme"]
            saved = stored.get("options")
            if isinstance(saved, dict):
                for key in prefs["options"]:
                    if isinstance(saved.get(key), bool):
                        prefs["options"][key] = saved[key]
        except (OSError, ValueError):
            pass  # a corrupt preferences file is not an error
    return prefs


def save_prefs(name, prefs):
    path = settings_path(name)
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh)
    except OSError:
        pass  # saving a preference is never worth an error


# ----------------------------------------------------------------------------- running
def find_python():
    """A real Python interpreter to run the build with.

    sys.executable is no use once this is frozen (it points at the launcher .exe), so the
    interpreter is resolved from PATH. `py` (the Windows launcher) is the fallback for
    machines where plain `python` isn't on PATH.
    """
    for name in ("python", "py"):
        found = shutil.which(name)
        if found:
            return found
    return None


def build_command(config, mode_index, option_values, python):
    """The exact command line the console runs (also used by --dry-run).

    `option_values` maps option id -> bool; each option contributes args_on or args_off.
    """
    args = list(config["modes"][mode_index]["args"]) if config["modes"] else []
    for option in config["options"]:
        args += option["args_on"] if option_values.get(option["id"]) else option["args_off"]
    return subprocess.list2cmdline([python, config["script"], *args])


def console_command(config, mode_index, option_values, python):
    """The whole `cmd /k` line: the build, then a final window title.

    cmd resets the console title when a program it started exits, which would wipe any
    "finished"/"FAILED" title the build script set. So cmd sets it again itself, from the
    build's exit code, and that one stays.
    """
    label = config["modes"][mode_index]["label"] if config["modes"] else "build"
    title = cmd_safe(f"{config['name']} build: {label}")
    return (f"{build_command(config, mode_index, option_values, python)} & if errorlevel 1 "
            f"(title {title} FAILED) else (title {title} finished)")


def dry_run(root):
    """Prints what the window would show and run, for checking a manifest without a GUI."""
    config = load_config(root)
    try:  # a legacy console codepage can't print the glyph/© ; don't die over a diagnostic
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(f"Root      : {config['root']}")
    print(f"Title     : {config['title']}")
    print(f"Header    : {(config['glyph'] + '  ') if config['glyph'] else ''}{config['name']} Build")
    print(f"Footer    : {config['footer']}")
    print(f"Script    : {config['script']} "
          f"({'found' if os.path.isfile(os.path.join(root, config['script'])) else 'MISSING'})")
    if config["warning"]:
        print(f"Warning   : {config['warning']}")
    print(f"Modes     : {len(config['modes'])}")
    for mode in config["modes"]:
        print(f"  ( ) {mode['label']} - {mode['desc']}  -> {mode['args']}")
    print(f"Options   : {len(config['options'])}")
    defaults = {o["id"]: o["default"] for o in config["options"]}
    for option in config["options"]:
        print(f"  [{'x' if option['default'] else ' '}] {option['label']}")
    print(f"Note      : {config['note']}")
    python = find_python() or "python"
    for index in range(max(len(config["modes"]), 1)):
        print("Command   :", console_command(config, index, defaults, python))


# --------------------------------------------------------------------------------- GUI
class BuildLauncher(tk.Tk if tk else object):
    def __init__(self, config):
        super().__init__()
        self.config_data = config
        self.name = config["name"]
        self.title(config["title"])
        self.resizable(False, False)
        self._set_icon()
        self.prefs = load_prefs(self.name, config["options"])
        self.theme_name = self.prefs["theme"]
        self.mode = tk.IntVar(value=0)
        self.option_vars = {o["id"]: tk.BooleanVar(value=self.prefs["options"][o["id"]])
                            for o in config["options"]}
        self.widgets = []  # (widget, role) pairs, repainted on theme change
        self._build_ui()
        self.apply_theme()
        self._centre()
        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self.run_build())
        if config["warning"]:
            self.set_status(config["warning"], error=True)

    def _set_icon(self):
        """The project's icon in the title bar instead of Tk's feather.

        Read from the project at run time (manifest "icon"), so one launcher build suits any
        project. Missing is fine; Tk keeps its default.
        """
        icon = self.config_data["icon"]
        if not icon:
            return
        path = os.path.join(self.config_data["root"], icon)
        if os.path.isfile(path):
            try:
                self.iconbitmap(default=path)
            except tk.TclError:
                pass

    # ----------------------------------------------------------------- layout
    def _styled(self, widget, role):
        """Tags a widget with a palette role so apply_theme() can repaint it.

        Not called _register: tkinter.Misc already has a _register that Tk uses while
        creating the window, and overriding it stops the window being created at all.
        """
        self.widgets.append((widget, role))
        return widget

    def _build_ui(self):
        config = self.config_data
        header = self._styled(tk.Frame(self), "nav")
        header.pack(fill="x")

        title_wrap = self._styled(tk.Frame(header), "nav")
        title_wrap.pack(side="left", padx=18, pady=(14, 12))
        heading = f"{config['glyph']}  {config['name']} Build" if config["glyph"] \
            else f"{config['name']} Build"
        self._styled(tk.Label(title_wrap, text=heading, font=(FONT, 15, "bold"),
                              anchor="w"), "nav-title").pack(anchor="w")
        self._styled(tk.Label(title_wrap, text=config["subtitle"], font=(FONT, 9),
                              anchor="w"), "nav-sub").pack(anchor="w")

        self.theme_btn = self._styled(
            tk.Button(header, width=3, relief="flat", cursor="hand2", font=(FONT, 11),
                      command=self.toggle_theme), "toggle")
        self.theme_btn.pack(side="right", padx=18)

        body = self._styled(tk.Frame(self), "bg")
        body.pack(fill="both", expand=True, padx=18, pady=16)

        # Only the modes the manifest lists get a card. A lone mode has nothing to choose, so
        # its card has no radio button.
        choosable = len(config["modes"]) > 1
        for index, mode in enumerate(config["modes"]):
            card = self._styled(tk.Frame(body, highlightthickness=1, bd=0), "card")
            card.pack(fill="x", pady=4)
            if choosable:
                name_widget = self._styled(
                    tk.Radiobutton(card, text=f"  {mode['label']}", value=index, variable=self.mode,
                                   font=(FONT, 10, "bold"), anchor="w", cursor="hand2",
                                   highlightthickness=0, bd=0, padx=10, pady=2), "radio")
            else:
                name_widget = self._styled(
                    tk.Label(card, text=f"  {mode['label']}", font=(FONT, 10, "bold"),
                             anchor="w", padx=10, pady=2), "card-title")
            name_widget.pack(fill="x", pady=(8, 0 if mode["desc"] else 8))
            if mode["desc"]:
                # The description sits under the name so the names stay scannable.
                caption = self._styled(
                    tk.Label(card, text=mode["desc"], font=(FONT, 9), anchor="w"), "caption")
                caption.pack(fill="x", padx=38, pady=(0, 8))
                if choosable:
                    caption.bind("<Button-1>", lambda _e, i=index: self.mode.set(i))
            if choosable:
                # Clicking anywhere on the card picks that mode.
                card.bind("<Button-1>", lambda _e, i=index: self.mode.set(i))

        for position, option in enumerate(config["options"]):
            box = self._styled(
                tk.Checkbutton(body, text=option["label"], variable=self.option_vars[option["id"]],
                               font=(FONT, 9), anchor="w", cursor="hand2",
                               highlightthickness=0, bd=0, command=self._remember_options), "check")
            box.pack(fill="x", pady=(10 if position == 0 else 4, 0))

        self.status = self._styled(
            tk.Label(body, text=config["note"], font=(FONT, 9), anchor="w", wraplength=440,
                     justify="left"), "status")
        self.status.pack(fill="x", pady=(6, 0))

        buttons = self._styled(tk.Frame(body), "bg")
        buttons.pack(fill="x", pady=(14, 0))
        self.run_btn = self._styled(
            tk.Button(buttons, text="Run", width=12, relief="flat", cursor="hand2",
                      font=(FONT, 10, "bold"), command=self.run_build), "primary")
        self.run_btn.pack(side="right")
        self.cancel_btn = self._styled(
            tk.Button(buttons, text="Cancel", width=12, relief="flat", cursor="hand2",
                      font=(FONT, 10), command=self.destroy), "secondary")
        self.cancel_btn.pack(side="right", padx=(0, 8))

        footer = self._styled(tk.Frame(self, highlightthickness=1, bd=0), "footer")
        footer.pack(fill="x", side="bottom")
        self._styled(tk.Label(footer, text=config["footer"], font=(FONT, 8), anchor="w"),
                     "footer-text").pack(side="left", padx=14, pady=7)
        readme = self._styled(tk.Label(footer, text="README", font=(FONT, 8, "bold"),
                                       cursor="hand2", anchor="e"), "footer-link")
        readme.pack(side="right", padx=14, pady=7)
        readme.bind("<Button-1>", lambda _e: self.open_readme())

    def _centre(self):
        self.update_idletasks()
        # A floor on the width so the longest description isn't pressed against the edge.
        w, h = max(self.winfo_width(), 480), self.winfo_height()
        self.geometry(f"{w}x{h}")
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------ theme
    def apply_theme(self):
        c = THEMES[self.theme_name]
        self.configure(bg=c["bg"])
        self.theme_btn.configure(text="☀" if self.theme_name == "dark" else "☾")

        styles = {
            "bg": dict(bg=c["bg"]),
            "nav": dict(bg=c["nav"]),
            "nav-title": dict(bg=c["nav"], fg=c["text"]),
            "nav-sub": dict(bg=c["nav"], fg=c["muted"]),
            "card": dict(bg=c["panel"], highlightbackground=c["border"],
                         highlightcolor=c["border"]),
            "card-title": dict(bg=c["panel"], fg=c["text"]),
            "radio": dict(bg=c["panel"], fg=c["text"], selectcolor=c["select"],
                          activebackground=c["panel"], activeforeground=c["accent"]),
            "caption": dict(bg=c["panel"], fg=c["muted"]),
            "check": dict(bg=c["bg"], fg=c["text"], selectcolor=c["select"],
                          activebackground=c["bg"], activeforeground=c["accent"]),
            "status": dict(bg=c["bg"], fg=c["muted"]),
            "primary": dict(bg=c["accent_fill"], fg=c["on_accent"],
                            activebackground=c["accent_fill"], activeforeground=c["on_accent"]),
            "secondary": dict(bg=c["panel"], fg=c["text"], activebackground=c["hover"],
                              activeforeground=c["text"]),
            "toggle": dict(bg=c["nav"], fg=c["accent"], activebackground=c["nav"],
                           activeforeground=c["accent"]),
            "footer": dict(bg=c["nav"], highlightbackground=c["border"],
                           highlightcolor=c["border"]),
            "footer-text": dict(bg=c["nav"], fg=c["muted"]),
            "footer-link": dict(bg=c["nav"], fg=c["accent"]),
        }
        for widget, role in self.widgets:
            widget.configure(**styles[role])

    def toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.prefs["theme"] = self.theme_name
        save_prefs(self.name, self.prefs)
        self.apply_theme()

    def _remember_options(self):
        self.prefs["options"] = {key: bool(var.get()) for key, var in self.option_vars.items()}
        save_prefs(self.name, self.prefs)

    # ----------------------------------------------------------------- actions
    def open_readme(self):
        readme = os.path.join(self.config_data["root"], self.config_data["readme"])
        if os.path.isfile(readme):
            os.startfile(readme)  # noqa: S606 (Windows-only by design)
        else:
            self.set_status(f"{self.config_data['readme']} not found in the project folder.",
                            error=True)

    def set_status(self, message, error=False):
        c = THEMES[self.theme_name]
        self.status.configure(text=message, fg=c["error"] if error else c["muted"])

    def run_build(self):
        config = self.config_data
        root = config["root"]
        if not os.path.isfile(os.path.join(root, config["script"])):
            messagebox.showerror(
                config["title"],
                f"Could not find {config['script']}.\n\nLooked in:\n{root}")
            return

        python = find_python()
        if not python:
            messagebox.showerror(
                config["title"],
                f"Could not find Python on PATH.\n\nThe launcher runs `python {config['script']}`, "
                "so Python needs to be callable as `python` or `py` from a command prompt.")
            return

        values = {key: bool(var.get()) for key, var in self.option_vars.items()}
        command = console_command(config, self.mode.get(), values, python)
        # `cmd /s /k` keeps the window open after the build so the output can be read.
        # /s makes cmd strip exactly the outer quotes, so a Python path containing spaces
        # survives. Passed as one string so list2cmdline doesn't re-quote the whole thing.
        try:
            subprocess.Popen(f'cmd /s /k "{command}"', cwd=root,
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        except OSError as exc:
            messagebox.showerror(config["title"], f"Could not start the build:\n\n{exc}")
            return

        # The console owns the build from here; staying open would only invite a second,
        # concurrent build into the same output folder.
        self.destroy()


def main(argv):
    dry = "--dry-run" in argv
    positional = [a for a in argv if not a.startswith("--")]
    root = find_project_root(positional[0] if positional else None)
    if not root:
        message = (f"Could not find {MANIFEST} or a build script.\n\nExpected them beside this "
                   "launcher or in the folder above it (tools/ -> the project root).")
        if dry or tk is None:
            print(message)
        else:
            hidden = tk.Tk()
            hidden.withdraw()
            messagebox.showerror("Build Launcher", message)
        return 1
    if dry:
        dry_run(root)
        return 0
    BuildLauncher(load_config(root)).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
