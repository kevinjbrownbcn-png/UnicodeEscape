# Pending Items

- [ ] Not tested: the Build Launcher's Run button against this project (window and mode list verified; a launcher-driven build wasn't run)
- [x] ~~No icon~~ — option A (navy tile, teal outline, teal `\u`) added in `assets/`; wired into the spec, `build_exe.py`, the window and the Build Launcher manifest
- [ ] Streamlit companion app not built — flagged as generally unsuitable per the native-OS-integration rule (this tool relies on `filedialog.askdirectory`, a native folder picker Streamlit can't replicate) rather than assumed out of scope. Revisit if a browser-based version is ever wanted (e.g. via file upload instead of folder selection).
- [x] ~~Escaped-separator keys mis-split~~ — fixed by the new line parser (review round 2)
- [ ] Review round 2 items not yet done: I/O errors (locked file, read-only output) still end the run with no dialog in the frozen exe; trailing-newline/CRLF handling is lossy and unlogged; UTF-8 BOM ends up in the first key; processing blocks the UI thread (log isn't live); settings JSON saved next to the exe; `regular` and `onefile` build the same exe; no `--skip-checks` / in-app dev-tools debug option; invalid-JSON-shape settings file crashes startup
- [x] ~~Escape non-ASCII keys~~ — decided to skip: keys and comments stay unescaped (documented in the README notes)
- [ ] No unit tests for `core.py` yet (ad-hoc checks only, including the new group logic)
- [x] ~~Character-group checkboxes verified from source only~~ — `regular` and `onedir` rebuilt with the icon; the exe launches with the group panel and new icon. Not rebuilt this round: `onefile`, `debug`; the exe wasn't re-run through a conversion after the groups change
- [x] ~~Settings file with non-object JSON crashes startup~~ — fixed in `theme.load_settings`
- [ ] Group checkboxes show names only (no example characters); the ranges/examples live in `core.GROUPS` and the README
- [x] ~~Re-run a build and smoke-test the exe after the core changes~~ — done (`build_exe.py regular`; exe converted a sample folder, copied a Latin-1 file unchanged, blocked output == input). Other three modes not rebuilt this round.
