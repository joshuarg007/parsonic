# Parsonic

**AI-Powered Visual Web Scraper** — Point, click, and let AI do the rest.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Studio: Axion Deep Labs](https://img.shields.io/badge/Studio-Axion_Deep_Labs-teal)](https://axiondeep.com/)

---

## Why Parsonic?

Most scrapers require coding. Visual scrapers require tedious clicking. **Parsonic combines AI intelligence with visual simplicity** — load a page, click "AI Analyze," and watch it automatically detect company names, phone numbers, emails, addresses, and more.

### AI-First Design

- **One-Click Field Detection** — AI analyzes page structure and identifies business data fields automatically
- **Smart Selector Generation** — Creates robust CSS selectors that work across similar pages
- **Intelligent Crawling** — Follows pagination and business links to discover more data
- **Local LLM Processing** — All AI runs locally via Ollama (no data leaves your machine)

---

## Key Innovations

| Feature | What It Does |
|---------|--------------|
| **AI Analyze** | Scans any page and auto-detects business fields (name, phone, email, address) in seconds |
| **Multi-Page Learning** | Run AI Analyze on different page types — selectors accumulate, building comprehensive extraction |
| **Smart Crawling** | Multiple link selectors let you follow both business links AND pagination |
| **Result Persistence** | Scraped data survives app restarts — pick up where you left off |
| **Auto-Validation** | Only saves results with actual business data (filters out empty/nav pages) |
| **Data Sanitization** | Automatically cleans `mailto:`, `tel:` prefixes from extracted data |
| **Thermal Safety** | Monitors GPU/CPU temps, auto-pauses AI to prevent overheating |

---

## Quick Start

```bash
# Clone
git clone https://github.com/joshuarg007/parsonic.git
cd parsonic

# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Run
python main.py
```

### Enable AI Features (Recommended)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Start & pull model
ollama serve &
ollama pull qwen2.5-coder:7b
```

---

## How It Works

### 1. Load Any Business Page
Enter a URL and hit Load. The embedded browser renders JavaScript-heavy sites.

### 2. AI Analyze
Click **"AI Analyze"** — the AI examines the page structure and detects:
- Company/business names
- Phone numbers (even behind "click to reveal" buttons)
- Email addresses
- Physical addresses
- Websites and social links

### 3. Navigate & Expand
Go to a different page type (listing vs detail) and run AI Analyze again. **Fields accumulate** — you're building a comprehensive extractor.

### 4. Set Up Crawling
Click any link in Select Mode → **"Add to Crawler"**. Add multiple selectors:
```
a.business-link      # Links to business detail pages
a.pagination-next    # "Next" button for more listings
```

### 5. Run & Export
Press **F6** to scrape. Results persist between sessions. Export to CSV/JSON anytime.

---

## Features

### Visual Scraping
- **Live Browser Preview** — See exactly what you're scraping
- **Select Mode** — Click elements to create selectors (no coding)
- **Smart Wizard** — AI suggests field names based on content

### AI Intelligence
- **Page Analysis** — Understands page structure, not just patterns
- **Reveal Button Detection** — Auto-clicks "show email/phone" buttons
- **Selector Healing** — AI suggests fixes when selectors break
- **Entity Normalization** — Standardizes company names and data

### Robust Crawling
- **Multi-Selector Support** — Follow business links + pagination
- **Duplicate Detection** — Skips already-scraped URLs
- **Same-Domain Filtering** — Stays on target site
- **Progress Tracking** — See crawl progress in real-time

### Data Quality
- **Auto-Validation** — Rejects entries without essential fields
- **Data Sanitization** — Cleans prefixes, normalizes whitespace
- **Persistent Storage** — Results saved to `~/.parsonic/results.json`
- **Deduplication** — Updates existing entries instead of duplicating

### Safety & Performance
- **Thermal Monitoring** — Pauses AI at 85°C CPU / 80°C GPU
- **Rate Limiting** — Adaptive delays, concurrent request limits
- **Stealth Mode** — Anti-detection for protected sites
- **Proxy Support** — Rotate through proxy pools

---

## Architecture

```
parsonic/
├── src/
│   ├── core/
│   │   ├── scraper.py          # Orchestrates crawling & extraction
│   │   ├── field_detection.py  # Pattern-based field detection
│   │   ├── llm_enrichment.py   # AI-powered page analysis
│   │   └── thermal_monitor.py  # Temperature safety
│   ├── engines/
│   │   ├── static_engine.py    # httpx + BeautifulSoup
│   │   └── js_engine.py        # Playwright for JS sites
│   ├── models/
│   │   └── project.py          # Pydantic schemas
│   └── ui/
│       ├── main_window.py      # PyQt6 application
│       ├── tabs/
│       │   ├── scrape_tab.py   # Main scraping interface
│       │   └── results_tab.py  # Results viewer + export
│       └── dialogs/
│           └── field_wizard.py # Smart field naming
└── main.py
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **GUI** | PyQt6 + PyQt6-WebEngine |
| **Browser** | Playwright + stealth patches |
| **Parsing** | BeautifulSoup, lxml |
| **AI/LLM** | Ollama (Qwen2.5-Coder) |
| **Data** | Pydantic, JSON persistence |
| **Async** | qasync, httpx |

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+N` | New project |
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save project |
| `F5` | Test single URL |
| `F6` | Run full scrape |
| `Esc` | Stop scraper |

---

## Requirements

- Python 3.10+
- 8GB RAM minimum
- GPU with 6GB+ VRAM (optional, for AI features)
- Ollama (optional, for AI features)

---

## Troubleshooting

**Browser won't load:** `playwright install chromium`

**AI features not working:** Make sure Ollama is running: `ollama serve`

**GPU temps showing N/A:** Requires `nvidia-smi` for NVIDIA GPUs

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for planned features.

---

## License


---

## Credits
Property of Axion Deep Labs Inc
Developed by Joshua R. Guierrez
*Parsonic: Because scraping should be smart, not hard.*
