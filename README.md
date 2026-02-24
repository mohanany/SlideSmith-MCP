# SlideSmith MCP

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

Turn your ideas into professional presentations with AI. Works with Claude, Cursor, Windsurf, OpenCode, and any MCP-compatible agent.

<p align="center">
  <img src="https://img.shields.io/badge/Claude-✅%20Supported-blue" alt="Claude">
  <img src="https://img.shields.io/badge/Windsurf-✅%20Supported-purple" alt="Windsurf">
  <img src="https://img.shields.io/badge/Cursor-✅%20Supported-yellow" alt="Cursor">
  <img src="https://img.shields.io/badge/OpenCode-✅%20Supported-orange" alt="OpenCode">
</p>

---

## 🎯 What Can SlideSmith Do For You?

### For Professionals
- **Sales Teams**: Create polished pitch decks in minutes
- **Marketers**: Generate brand presentations at scale
- **Consultants**: Produce client reports instantly
- **Educators**: Build engaging lesson slides

### For Developers
- **Technical Demos**: Architecture diagrams, API docs
- **Project Proposals**: Visual guides and documentation
- **Team Updates**: Sprint reviews and status reports

---

## � Prerequisites

Before starting, ensure you have:

- **Python 3.10 or higher** (`python --version`)
- **uv** (recommended) or **pip** package manager
- **Git** (`git --version`)
- **LibreOffice** (optional, only needed for PDF export)

### Install uv (Recommended)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install LibreOffice (Optional - for PDF export)
```bash
# Ubuntu/Debian
sudo apt install libreoffice

# macOS
brew install --cask libreoffice

# Windows (with chocolatey)
choco install libreoffice
```

---

## �🚀 Quick Start

### Step 1: Clone & Install
```bash
git clone https://github.com/mohanany/slidesmith-mcp.git
cd slidesmith-mcp
uv venv && source .venv/bin/activate
uv pip install -e .
```

### Step 2: Install Browser (for Playwright)
```bash
playwright install chromium
```

### Step 3: Test Installation
```bash
slidesmith --help
```

### Step 4: Connect Your AI Agent

Add this to your AI agent's MCP configuration:

```json
{
  "mcpServers": {
    "slidesmith": {
      "command": "uv",
      "args": ["--directory", "/path/to/slidesmith-mcp", "run", "slidesmith"]
    }
  }
}
```

---

## 💡 Example Usage

Just tell your AI agent:

> *"Create a 5-slide pitch deck for a fintech startup"*

The AI handles:
- Professional slide design
- Finding and embedding relevant images
- Exporting both PowerPoint and PDF

---

## 🎨 Available Themes

- **Business**: Corporate presentations, reports
- **Deep Tech**: Technical demos, AI/ML content
- **Futuristic**: Innovation pitches
- **Sophisticated**: Luxury brands, high-end services
- **Minimal**: Clean, distraction-free content
- **Dark Mode**: Developer presentations

---

## 🔧 Troubleshooting

### "playwright not found" error
```bash
uv run playwright install chromium
```

### "libreoffice not found" error (PDF export fails)
Install LibreOffice using instructions in Prerequisites section above.

### Permission denied on macOS/Linux
```bash
chmod +x .venv/bin/slidesmith
```

### Images not appearing in presentations
This is normal if using raw URLs. The tool automatically embeds images to prevent broken links.

---

## 📄 License

Apache 2.0 — See [LICENSE](./LICENSE)
