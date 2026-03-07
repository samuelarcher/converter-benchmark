# Converter Benchmark

A developer tool for rapidly assessing open-source file conversion tools for accuracy and fidelity. Upload documents, run multiple converters in parallel, score results with Claude, and review outputs side-by-side.

## Features

- **Pluggable converters** — drop a single file into `converters/` to add a new converter; zero other changes needed
- **Multiple output formats** — markdown, HTML, plain text, JSON; global default overridable per run
- **LLM scoring** — Claude grades each conversion against a plain-text baseline using a per-format rubric
- **Manual review** — three-pane side-by-side UI with human scoring (1–5) and notes
- **Persistent results** — SQLite stores every conversion and score; re-runs are idempotent

## Supported Converters

| Converter | Formats | Requires |
|-----------|---------|----------|
| [MarkItDown](https://github.com/microsoft/markitdown) | markdown, text | Python package |
| [pdfminer.six](https://github.com/pdfminer/pdfminer.six) | text | Python package |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | text, json | Python package |
| [Pandoc](https://pandoc.org) | markdown, html, text | `pandoc` CLI |
| [LibreOffice](https://www.libreoffice.org) | markdown, html, text | `soffice` CLI |

## Requirements

- Python 3.13+
- `pandoc` and/or `soffice` CLIs (optional — only needed for those converters)
- An Anthropic API key (optional — only needed for LLM scoring)

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/samuelarcher/converter-benchmark.git
cd converter-benchmark

# 2. Create and activate a virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install flask markdown anthropic markdownify pdfminer.six pdfplumber markitdown

# 4. (Optional) Install system tools for full converter support
brew install pandoc libreoffice   # macOS
# apt install pandoc libreoffice  # Debian/Ubuntu

# 5. Set your Anthropic API key (required for LLM scoring)
export ANTHROPIC_API_KEY=sk-ant-...
```

## Running

```bash
cd converter-benchmark
source .venv/bin/activate
flask run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

For non-thread-safe converters (MarkItDown), run with `--no-debugger` and without threading:

```bash
flask run --no-debugger
# or
python app.py
```

## Directory Structure

```
benchmark/
├── app.py                    # Flask app + all routes
├── db.py                     # SQLite schema + query helpers
├── config.py                 # Global defaults (output format)
├── converters/
│   ├── __init__.py           # Auto-discovery registry
│   ├── base.py               # ConverterPlugin base class + ConversionResult
│   ├── markitdown_conv.py
│   ├── pandoc_conv.py
│   ├── libreoffice_conv.py
│   ├── pdfminer_conv.py
│   └── pdfplumber_conv.py
├── scoring/
│   └── llm_scorer.py         # Claude API scoring
├── templates/
│   ├── base.html
│   ├── index.html            # Upload, folder scan, document list
│   ├── results.html          # Per-document converter results
│   └── review.html           # Side-by-side review + manual scoring
├── uploads/                  # Uploaded files (gitignored)
└── benchmark.db              # SQLite database (gitignored)
```

## Adding a Converter

1. Create `converters/my_converter.py`
2. Subclass `ConverterPlugin` and set a unique `name`

```python
from converters.base import ConverterPlugin, ConversionResult
from pathlib import Path

class MyConverter(ConverterPlugin):
    name = "my_converter"
    label = "My Converter"
    supported_extensions = [".pdf", ".docx"]
    supported_output_formats = ["text"]

    def convert(self, file_path: Path, output_format: str) -> ConversionResult:
        if output_format not in self.supported_output_formats:
            return self._unsupported(output_format)
        # ... conversion logic ...
        return ConversionResult(
            converter_name=self.name,
            output_format=output_format,
            content="...",
        )
```

The converter is automatically discovered and registered on next startup.

## LLM Scoring

Scoring is triggered via the **Run LLM Scoring** button on the results page or `POST /doc/<id>/llm-score`. Claude uses pdfminer's plain-text output as a neutral reference baseline (falls back to the first non-empty conversion). Scores are stored per conversion and per output format.

**Rubrics by format:**

| Format | Criteria |
|--------|----------|
| markdown / html | content_completeness, structure_preservation, table_accuracy, formatting_fidelity, readability, overall |
| text | content_completeness, readability, overall |
| json | content_completeness, schema_consistency, table_accuracy, overall |

## Routes

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Document list, upload form, folder scan, format setting |
| POST | `/settings` | Update global default output format |
| POST | `/upload` | Upload a file |
| POST | `/scan` | Walk a folder and import all supported files |
| GET | `/doc/<id>` | Converter results for a document |
| POST | `/doc/<id>/run` | Run selected converters with chosen format |
| GET | `/doc/<id>/review` | Side-by-side review UI |
| POST | `/doc/<id>/score` | Save human scores |
| POST | `/doc/<id>/llm-score` | Trigger Claude scoring |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For LLM scoring | Anthropic API key |
| `FLASK_SECRET` | No | Flask session secret (defaults to a dev value) |
