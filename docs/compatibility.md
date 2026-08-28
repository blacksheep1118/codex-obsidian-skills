# Compatibility

| Area | Supported | Notes |
| --- | --- | --- |
| Python | 3.9, 3.11, 3.12 | CI validates Python 3.9, 3.11, and 3.12 on Ubuntu, plus Python 3.11 on macOS and Windows. Python 3.10 is outside the current matrix. |
| Operating systems | macOS, Windows, Linux | Install, update, validation, path handling, and source collection are documented for macOS/Linux shells and Windows PowerShell. |
| Install paths | `~/.codex/skills`, `%USERPROFILE%\.codex\skills`, `CODEX_HOME/skills` | Management scripts use `Path.home()` by default and accept `--destination` or `--codex-home` on every platform. |
| Obsidian links | Markdown links, `[[wiki]]`, `[[path/to/file]]`, `[[path/to/file|alias]]` | Link checking resolves relative paths, root-relative paths, stems, anchors, queries, and URL-encoded spaces. |
| PPTX extraction | `.pptx` | Uses `python-pptx`. |
| Legacy PPT conversion | `.ppt` | Requires LibreOffice on `PATH`, a standard macOS/Windows install path, or an explicit executable path passed with `--soffice`. |
| PDF extraction | `.pdf` | Tries `pypdf`, then `pdfplumber` when installed, then the `pdftotext` command when available. |
| Web source collection | URLs, local HTML files, direct PDF/PPT/book/transcript URLs | `web-course-notes-for-obsidian` uses the Python standard library for page titles, descriptions, learning-resource link discovery, direct-resource classification, note-folder creation, and platform-aware `file://` path handling. |
| Notes-to-PPT planning | Markdown files, Obsidian notes, note folders | `notes-to-scientific-ppt` uses the Python standard library to inventory headings, links, tables, images, formulas, and source coverage before PPTX construction. |
| Validation dependencies | `pytest`, `PyYAML`, `ruff` | Installed from the root or skill-local `requirements-dev.txt` as applicable; the tool profiles require all three. |
| PPT/PDF extraction runtime | `python-pptx`, `PyYAML`, `pypdf` | Installed from `skill/ppt-to-md-for-obsidian/requirements.txt`; `pdfplumber` and the system `pdftotext` command are optional PDF fallbacks. |
| Notes-to-PPT runtime | `python-pptx` | Installed from `skill/notes-to-scientific-ppt/requirements.txt`. |
| Dependency-backed note runtime | Python 3.10+, Java 17+, pinned NumPy/PyTorch/ONNX/ONNX Runtime/ONNXScript/PySpark | Kept separate in `skill/algorithm-job-notes-for-obsidian/requirements-runtime.txt`; used only by the explicit `vault-runtime` profile. |
