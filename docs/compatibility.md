# Compatibility

| Area | Supported | Notes |
| --- | --- | --- |
| Python | 3.9, 3.11, 3.12 | CI validates Python 3.9, 3.11, and 3.12 on Ubuntu, plus Python 3.11 on macOS and Windows. Python 3.10 should also work but is not part of the current matrix. |
| Operating systems | macOS, Windows, Linux | Install, update, validation, path handling, and source collection are documented for macOS/Linux shells and Windows PowerShell. |
| Install paths | `~/.codex/skills`, `%USERPROFILE%\.codex\skills`, `CODEX_HOME/skills` | Management scripts use `Path.home()` by default and accept `--destination` or `--codex-home` on every platform. |
| Obsidian links | Markdown links, `[[wiki]]`, `[[path/to/file]]`, `[[path/to/file|alias]]` | Link checking resolves relative paths, root-relative paths, stems, anchors, queries, and URL-encoded spaces. |
| PPTX extraction | `.pptx` | Uses `python-pptx`. |
| Legacy PPT conversion | `.ppt` | Requires LibreOffice on `PATH`, a standard macOS/Windows install path, or an explicit executable path passed with `--soffice`. |
| PDF extraction | `.pdf` | Uses `pypdf`; can use `pdfplumber` when installed. |
| Web source collection | URLs, local HTML files, direct PDF/PPT/book/transcript URLs | `web-course-notes-for-obsidian` uses the Python standard library for page titles, descriptions, learning-resource link discovery, direct-resource classification, note-folder creation, and platform-aware `file://` path handling. |
| Validation dependencies | `pytest`, `PyYAML` | Installed from skill-local `requirements-dev.txt`. |
| Runtime dependencies | `python-pptx`, `PyYAML`, `pypdf` | Installed from `skill/ppt-to-md-for-obsidian/requirements.txt`. |
