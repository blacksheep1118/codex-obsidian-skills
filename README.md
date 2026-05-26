# skill-ppt-to-md-for-obsidian

Codex skill for converting PPT/PPTX courseware into Obsidian-ready Markdown notes.

The skill is designed for lecture slides that need to become usable study notes, not slide transcripts. It emphasizes Chinese course notes, formulas, numbered chapter files, course maps, cross-links, and detailed plus concise review pages.

## What It Produces

- Obsidian Markdown chapter notes.
- `00_课程总览.md` or `00_学习地图.md` navigation pages.
- `知识点详细版_含公式.md` full review pages.
- `知识点精简复习版_含公式.md` fast review pages.
- Cross-course wiki links using Obsidian syntax.

## Repository Layout

```text
.
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
├── scripts/
│   └── extract_pptx_text.py
└── references/
    ├── obsidian-style.md
    └── validation.md
```

## Usage

Install or copy this repository as a Codex skill, then ask Codex to convert courseware into Obsidian notes.

Example prompts:

```text
把这个课程 PPT 转成 Obsidian 笔记，保留公式解释和章节导航。
```

```text
检查这个 notes 目录，补课程总览、详细复习版和精简复习版。
```

```text
把新增 PPT 合并进已有笔记，不要移动源资料。
```

## PPTX Text Extraction

For deterministic extraction from `.pptx`:

```bash
python3 scripts/extract_pptx_text.py path/to/slides.pptx --out extracted.md
```

The script extracts slide text, table cells, and speaker notes when available. It is intended as a raw input aid; Codex should still rewrite the output into clean notes.

## Design Principles

- Source files are read-only by default.
- Markdown outputs should be study notes, not slide dumps.
- Formulas need nearby variable explanations.
- Links should be placed where concepts first appear.
- Detailed and concise review pages should both be preserved.

## License

Add a license if this repository will be shared publicly.
