# Architecture

Internal design of `batch_extract.py` — how each component works.

---

## Data Flow Overview

```
PDF file
    │
    ▼
sha256_file()          ← checksum for identification
    │
    ▼
detect_header_footer_strings()
    │  Scans ALL pages once
    │  Collects first and last 2 blocks from each page
    │  Strings appearing on ≥ 40% of pages → headers/footers
    │  Pages with varying numbers ("Chapter 3 — 42") normalized:
    │  digits replaced with "#" before comparison
    │
    ▼
For each page:
    │
    ├─ extract_page()
    │       │
    │       ├─ _extract_links()          page.get_links() → {rect: uri}
    │       │
    │       ├─ _detect_footnotes()       page.get_text("dict") → font sizes
    │       │   Finds blocks in bottom 25% of page with font < 85% of main text
    │       │
    │       ├─ page.find_tables()        PyMuPDF built-in table detector
    │       │   └─ _table_to_markdown()  → markdown with fallback to plain cells
    │       │
    │       ├─ page.get_text("blocks")   All text blocks with coordinates
    │       │   ├─ Skip footnote blocks (by index from _detect_footnotes)
    │       │   ├─ Skip blocks inside tables (rect intersection)
    │       │   ├─ Skip headers/footers (_is_header_footer)
    │       │   └─ _assign_columns()     Cluster blocks by x-center
    │       │       Sort: (col_index, y) — column-first, then top-to-bottom
    │       │
    │       ├─ Embedded images           page.get_images(full=True)
    │       │   ├─ Filter by W×H        (img-min-px)
    │       │   ├─ _bytes_to_rgb()       PIL decoding
    │       │   └─ ocr_engine.predict()  → _parse_ocr_result() with confidence filter
    │       │
    │       ├─ Full-page OCR            if native_chars < min-native
    │       │   ├─ page.get_pixmap()     render at DPI
    │       │   ├─ _pix_to_rgb()
    │       │   └─ ocr_engine.predict()  → _parse_ocr_result()
    │       │
    │       └─ Assembly: text + tables + image_ocr + footnotes + links
    │
    ├─ _merge_cross_page_paragraphs()
    │   If end of page N is not . ! ? and
    │   start of page N+1 is lowercase → merge
    │
    └─ Save .txt and .manifest.json
    
chunk_text()            Sliding window over words
    │
    ▼
train.jsonl             {"text": "..."} — one entry = one chunk
```

---

## Components

### `PageReport` and `PDFManifest`

Python dataclasses. Serialized via `dataclasses.asdict()` to JSON without field loss. All values are preserved — counters incremented explicitly.

### `detect_header_footer_strings(doc)`

```python
# Normalization: "Chapter 3 — 42" → "chapter # — #"
def _normalise(s): return re.sub(r"\b\d+\b", "#", s.strip().lower())

# Threshold: 40% of pages must have this string
threshold = max(2, int(n * 0.40))
```

Checks first 2 and last 2 text blocks on each page. Covers 99% of book headers/footers without capturing content.

### `_assign_columns(blocks, page_width)`

Algorithm:
1. Computes x-center of each block: `(x0 + x1) / 2`
2. Sorts all unique x-centers
3. Finds gaps between adjacent centers > 15% of page width
4. Each gap = column boundary
5. Assigns blocks to column indices, sorts by `(col_index, y0)`

Example for two-column page (width 595pt):
```
Blocks with x-center 120–150pt → column 0
Gap ~250pt (> 595 * 0.15 = 89pt) → boundary
Blocks with x-center 380–420pt → column 1
Result: all column 0 blocks read before column 1 blocks
```

### `_detect_footnotes(page)`

1. Gets `page.get_text("dict")` — detailed format with font sizes
2. Finds most common font size = main text
3. Blocks in bottom 25% of page with font < 85% of main → footnotes
4. Returns block indices to exclude from main text

### `_parse_ocr_result(items, conf_threshold)`

PaddleOCR returns list of prediction objects. Each has:
- `rec_texts` — list of lines
- `rec_scores` — corresponding confidence scores (0.0–1.0)

Lines with `score < conf_threshold` are discarded and counted in `ocr_lines_dropped`. Critical for poor-quality scans — prevents OCR garbage from entering dataset.

### `_merge_cross_page_paragraphs(pages_text)`

```python
_SENTENCE_END = re.compile(r'[.!?…»"''")\]>]\s*$')  # sentence end
_STARTS_LOWER = re.compile(r'^\s*[a-z]')             # lowercase letter

# If previous page does NOT end with punctuation
# AND current page starts with lowercase letter → merge
```

Handles case where PDF reader splits paragraph at page boundary.

### `chunk_text(text, chunk_size, overlap)`

Sliding window over words (not tokens, not characters):

```
words = text.split()
for i in range(0, len(words), chunk_size - overlap):
    chunk = words[i : i + chunk_size]
```

Overlap (`overlap=64`) ensures context at chunk boundaries is preserved during training.

---

## Error Handling

Each operation wrapped in `try/except`:

| Level | Behavior on Error |
|---|---|
| `fitz.open()` | PDF skipped, error recorded in manifest and log |
| `load_page()` | Page marked `method=failed`, processing continues |
| `find_tables()` | Warning, tables skipped, text extracted |
| `extract_image()` | Warning, image skipped |
| `ocr_engine.predict()` | Warning, OCR skipped |
| Entire PDF | Critical error, PDF skipped, others continue |

No error interrupts the entire batch. All errors are recorded.

---

## Quality Control System

After extracting all PDFs, quality control system runs automatically:

### `compute_quality_metrics(manifest: dict) -> QualityMetrics`

Analyzes each PDF manifest and computes:
- `avg_confidence` — average OCR confidence score (0.0–1.0)
- `min_confidence` — minimum confidence in PDF
- `pages_low_confidence` — list of pages with confidence < 0.70
- `pages_very_low_quality` — list of pages with < 50 characters (empty/corrupted)
- `issue_severity` — "ok" | "warning" | "critical"

Severity rules:
- **CRITICAL**: avg_conf < 0.50 OR > 30% of pages low quality
- **WARNING**: avg_conf < 0.65 OR > 15% of pages low quality
- **OK**: all good

### `generate_health_report(metrics_list, out_path) -> str`

Generates text report with sections:

1. **CRITICAL ISSUES** — PDFs that need reprocessing
2. **WARNINGS** — PDFs that can be filtered
3. **GOOD PDFs** — ready for training
4. **AUTO-GENERATED REPAIR RECIPES** — commands to reprocess

Example repair recipe for Book1.pdf with low confidence:
```bash
python batch_extract.py '<pdf_dir>/Book1.pdf' --dpi 350 --conf 0.4 --reprocess
```

### `filter_low_quality_chunks(jsonl_in, manifests, quality_metrics, out_dir) -> tuple[int, int]`

Splits train.jsonl into two parts:

1. **train.jsonl** — chunks from high-quality pages only
2. **train.lowquality.jsonl** — chunks from problem pages for manual review

Identification: each chunk contains page header like `[book_name:PAGE 5/100 | OCR]`. Function checks if such page markers exist in chunk for problem pages.

---

## Dependencies and Their Roles

```
fitz (PyMuPDF)
  ├─ fitz.open()           — open PDF
  ├─ page.get_text()       — native text in various formats
  ├─ page.find_tables()    — detect and extract tables
  ├─ page.get_images()     — list embedded images
  ├─ doc.extract_image()   — image bytes by xref
  ├─ page.get_links()      — hyperlinks
  ├─ page.get_pixmap()     — render page to bitmap
  └─ fitz.Pixmap           — bitmap operations

paddleocr.PaddleOCR
  └─ .predict(np.ndarray)  — OCR image

PIL.Image (pillow)
  └─ Image.open()          — decode embedded images

numpy
  └─ np.frombuffer()       — convert pixmap bytes to array
```
