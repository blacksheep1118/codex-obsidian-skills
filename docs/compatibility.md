# Compatibility

| Area | Supported | Notes |
| --- | --- | --- |
| Python | 3.9, 3.11, 3.12 | CI validates these versions. Python 3.10 should also work but is not part of the current matrix. |
| Operating systems | macOS, Linux | CI runs on Ubuntu. macOS is the primary local authoring environment. |
| Obsidian links | Markdown links, `[[wiki]]`, `[[path/to/file]]`, `[[path/to/file|alias]]` | Link checking resolves relative paths, root-relative paths, stems, anchors, queries, and URL-encoded spaces. |
| PPTX extraction | `.pptx` | Uses `python-pptx`. |
| Legacy PPT conversion | `.ppt` | Requires LibreOffice on `PATH` or an explicit executable path. |
| PDF extraction | `.pdf` | Uses `pypdf`; can use `pdfplumber` when installed. |
| Web source collection | URLs, local HTML files | `web-course-notes-for-obsidian` uses the Python standard library for page titles, descriptions, and learning-resource link discovery. |
| Validation dependencies | `pytest`, `PyYAML` | Installed from skill-local `requirements-dev.txt`. |
| Runtime dependencies | `python-pptx`, `PyYAML`, `pypdf` | Installed from `skill/ppt-to-md-for-obsidian/requirements.txt`. |
