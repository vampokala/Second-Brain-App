Below is a **clean, copy‑paste‑friendly Markdown cheat sheet** for **Cursor IDE shortcuts**, with special focus on **Python development workflows**. Cursor is a VS Code–based editor, so **VS Code shortcuts apply**, plus **Cursor‑specific AI shortcuts** that dramatically improve Python productivity.

> **Notation**
> 
> - **Mac** uses `⌘` (Command)
> - **Windows / Linux** uses `Ctrl`
> - I show shortcuts as **Mac / Windows‑Linux**

---

# 🧠 Cursor IDE – Python Developer Shortcut Cheat Sheet

---

## 🚀 Core Cursor AI Shortcuts (Most Important)

### 🔹 Inline AI Editing (Python refactors, fixes, docs)

```
⌘K  /  Ctrl+K
```

- Edit selected Python code using natural language
- Examples: _“Convert to async”_, _“Add type hints”_, _“Optimize this loop”_ [[cursor.com]](https://cursor.com/docs/configuration/kbd), [[cursor101.com]](https://cursor101.com/en/cursor/cheat-sheet)

---

### 🔹 AI Chat (Ask about codebase)

```
⌘L  /  Ctrl+L
```

- Ask questions about Python files, functions, or the whole repo
- Works great with selected code [[cursor.com]](https://cursor.com/docs/configuration/kbd)

---

### 🔹 Composer / Agent Mode (Multi‑file Python changes)

```
⌘I  /  Ctrl+I
⌘⇧I / Ctrl+Shift+I  (fullscreen)
```

- Refactor multiple Python files at once
- Ideal for migrations, API changes, architecture edits [[refined.so]](https://refined.so/blog/cursor-shortcuts-guide)

---

### 🔹 Accept AI Suggestions

```
Tab                → Accept full suggestion
⌘→ / Ctrl+→        → Accept next word
Esc                → Reject suggestion
```

- Cursor has **multi‑line Python predictions** (stronger than Copilot) [[design.dev]](https://design.dev/guides/cursor-shortcuts/)

---

## 🐍 Python‑Specific Coding Shortcuts

### 🔹 Comment / Uncomment Code

```
⌘/  /  Ctrl+/
```

- Line comments (`#`) for Python [[design.dev]](https://design.dev/guides/cursor-shortcuts/)

---

### 🔹 Format Python Code

```
⌥⇧F / Alt+Shift+F        → Format file
⌘K ⌘F / Ctrl+K Ctrl+F   → Format selection
```

- Uses configured formatter (`black`, `autopep8`, etc.) [[design.dev]](https://design.dev/guides/cursor-shortcuts/)

---

### 🔹 Go to Symbol (Functions / Classes)

```
⌘⇧O / Ctrl+Shift+O
```

- Jump between Python methods quickly [[developerupdates.com]](https://www.developerupdates.com/cheatsheets/cursor)

---

### 🔹 Go to Definition

```
F12
```

- Jump to function/class definition [[developerupdates.com]](https://www.developerupdates.com/cheatsheets/cursor)

---

### 🔹 Rename Symbol (Refactor)

```
F2
```

- Safely rename variables, functions, classes across Python files [[developerupdates.com]](https://www.developerupdates.com/cheatsheets/cursor)

---

## ✂️ Editing & Navigation (Muscle Memory)

### 🔹 File Navigation

```
⌘P  /  Ctrl+P   → Quick open file
⌘B  /  Ctrl+B   → Toggle sidebar
⌘`  /  Ctrl+`   → Toggle terminal
```

[[design.dev]](https://design.dev/guides/cursor-shortcuts/)

---

### 🔹 Line Editing

```
⌥↑ / Alt+↑      → Move line up
⌥↓ / Alt+↓      → Move line down
⇧⌥↑ / Shift+Alt+↑ → Duplicate line
```

[[design.dev]](https://design.dev/guides/cursor-shortcuts/)

---

### 🔹 Multi‑Cursor (Extremely useful in Python)

```
⌥Click / Alt+Click       → Add cursor
⌘D / Ctrl+D              → Select next occurrence
⌘⇧L / Ctrl+Shift+L       → Select all occurrences
```

[[design.dev]](https://design.dev/guides/cursor-shortcuts/)

---

## 🧪 Running & Terminal (Python Dev)

### 🔹 Open Terminal

```
⌘`  /  Ctrl+`
```

### 🔹 Run AI‑Generated Command

```
Enter
```

(after Cursor proposes a terminal command) [[cursor.com]](https://cursor.com/docs/configuration/kbd)

---

## 🧭 Code Folding (Clean Python Views)

```
Fold all:     ⌘R 0  /  Ctrl+K Ctrl+0
Unfold all:   ⌘R J  /  Ctrl+K Ctrl+J
```

[[stackoverflow.com]](https://stackoverflow.com/questions/79704381/collapse-all-methods-in-cursor-ai-editor)

---

## 📎 Context & References for AI (Python‑Specific Power)

### 🔹 Add Python code to AI context

```
Select code → ⌘⇧L / Ctrl+Shift+L
```

### 🔹 Mention files / symbols in prompts

```
@filename.py
@function_name
@variable_name
```

[[cursor101.com]](https://cursor101.com/en/cursor/cheat-sheet)

---

## ⚙️ Command Palette & Settings

### 🔹 Command Palette

```
⌘⇧P / Ctrl+Shift+P
```

### 🔹 Cursor Settings

```
⌘⇧J / Ctrl+Shift+J
```

[[cursor.com]](https://cursor.com/docs/configuration/kbd)

---

## 🧠 Pro Python Workflow Tips (Cursor‑Only)

- Use **⌘K on selected functions** to:
    - Add type hints
    - Convert sync → async
    - Generate docstrings
    - Write pytest tests
- Use **Composer (⌘I)** for:
    - Django / FastAPI refactors
    - Folder‑wide API changes
    - Data model migrations
- Cursor respects `.gitignore` and `.cursorignore` when indexing Python files [[kidpeterpa….github.io]](https://kidpeterpan.github.io/cheatsheet/Cursor-Cheat-Sheet)

---

## 📚 Official References

- [Cursor Keyboard Shortcuts – Official Docs](https://cursor.com/docs/configuration/kbd)
- [Cursor AI Cheat Sheet](https://cursor101.com/en/cursor/cheat-sheet)
- [VS Code & Cursor Shared Shortcuts](https://design.dev/guides/cursor-shortcuts/)

---

If you want, I can:

- 📄 Export this as **PDF**
- 🖨️ Make a **one‑page printable version**
- 🐍 Create a **Python‑only minimal cheat sheet**
- ⚙️ Customize shortcuts around **your OS or workflow**

Just tell me 👍