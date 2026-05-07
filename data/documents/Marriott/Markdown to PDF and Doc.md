
Here’s what was added and how to use it.

## Global skill: `markdown-pdf-docx-layout`

Location: `~/.cursor/skills/markdown-pdf-docx-layout/`

|File|Purpose|
|---|---|
|SKILL.md|When to use it, prerequisites, commands, limits|
|`scripts/mermaid_preprocess.py`|Turns ` ```mermaid ` blocks into PNGs via `mmdc`|
|`scripts/md-export.sh`|Preprocess → Pandoc → `.docx` and/or `.pdf`|
|`scripts/pdf-header.tex`|LaTeX extras for tables/images in PDF|

Cursor should pick up personal skills under `~/.cursor/skills/` automatically. If it doesn’t, open Cursor Settings → Rules / Skills (or your Skills UI) and confirm that folder is included.

---

## Prerequisites

1. Pandoc: `brew install pandoc`
2. Mermaid CLI: `npm install -g @mermaid-js/mermaid-cli` (command: `mmdc`)
3. PDF only: a LaTeX install (e.g. BasicTeX / MacTeX) so `--pdf-engine=pdflatex` works

---

## Run it (example: your integration doc)

# Word + PDF next to the markdown file

~/.cursor/skills/markdown-pdf-docx-layout/scripts/md-export.sh \

"/Users/vpoka217/Downloads/docs/TIPAI-INTEGRATION.md" \

both

DOCX only: use `docx` instead of `both`. PDF only: use `pdf`.

Custom output prefix (no extension; parent directory must exist):

~/.cursor/skills/markdown-pdf-docx-layout/scripts/md-export.sh \

"/Users/vpoka217/Downloads/docs/TIPAI-INTEGRATION.md" \

both \

"/Users/vpoka217/Downloads/docs/TIPAI-INTEGRATION-export"

Optional Word template (borders, heading styles):

export REFERENCE_DOCX="/path/to/your/reference.docx"

~/.cursor/skills/markdown-pdf-docx-layout/scripts/md-export.sh "/path/to/file.md" docx

Optional PDF engine (e.g. Unicode):

export PDF_ENGINE=xelatex

~/.cursor/skills/markdown-pdf-docx-layout/scripts/md-export.sh "/path/to/file.md" pdf

---

## What gets written beside the `.md`

- `<stem>.export.md` — same content with Mermaid replaced by `![...](...)` images
- `<stem>_mermaid_assets/` — `diagram-1.mmd`, `diagram-1.png`, …
- `<stem>.docx` / `<stem>.pdf` (or your chosen basename)

---

## Fidelity notes

- Tables & structure: Pandoc with `pipe_tables` + `grid_tables`, `--toc`, `--number-sections`.
- Mermaid: Rendered to PNG first (Pandoc cannot render Mermaid by itself), including diagrams with `%%{init: ...}%%` like in your sample.
- Perfect Word table chrome: Use a reference DOCX with a proper Table style.
- HTML in Markdown: Supported as `raw_html` where Pandoc can map it; heavy HTML may need cleanup.

If `chmod` was never run on your machine for these scripts, run:

chmod +x ~/.cursor/skills/markdown-pdf-docx-layout/scripts/md-export.sh \

~/.cursor/skills/markdown-pdf-docx-layout/scripts/mermaid_preprocess.py