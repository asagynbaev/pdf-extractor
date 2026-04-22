# Output File Formats

---

## `<stem>.txt` — Document Text

Full extracted text from a single PDF. UTF-8 encoded, structured.

### Structure

```
[BookName:PAGE 1/312 | NATIVE]
<text from first page>

[TABLE]
| Column 1 | Column 2 |
|----------|----------|
| Data     | Data     |
[/TABLE]

[BookName:PAGE 2/312 | OCR]
<text from OCR-processed page>

[IMAGE_OCR]
<text extracted from embedded image>
[/IMAGE_OCR]

[FOOTNOTES]
  * Footnote text
[/FOOTNOTES]

[LINKS]
  [1] https://example.com
[/LINKS]
```

### Markers

| Marker | Meaning |
|---|---|
| `[PDFName:PAGE N/TOTAL \| METHOD]` | Page start. Includes PDF filename for quality filtering. METHOD: NATIVE / OCR / HYBRID / FAILED |
| `[TABLE]...[/TABLE]` | Table in markdown format |
| `[IMAGE_OCR]...[/IMAGE_OCR]` | Text extracted from embedded image |
| `[FOOTNOTES]...[/FOOTNOTES]` | Page footnotes (collected from bottom of page) |
| `[LINKS]...[/LINKS]` | Hyperlinks from page |
| `[NO TEXT]` | Page with no extracted content (marked for audit) |

---

## `<stem>.manifest.json` — Document Report

Detailed JSON report for each page of each PDF. Created simultaneously with `.txt`.

### Example

```json
{
  "pdf_path": "C:/Books/Hacking_Art.pdf",
  "pdf_sha256": "a3f9d2c1e4b5...",
  "extracted_at": "2026-04-22T10:30:00+00:00",
  "total_pages": 312,
  "total_chars": 847293,
  "pages_native": 289,
  "pages_ocr": 18,
  "pages_hybrid": 5,
  "pages_failed": 0,
  "tables_total": 34,
  "links_total": 127,
  "images_ocrd_total": 12,
  "low_quality_pages": [45, 178],
  "errors": [],
  "pages": [
    {
      "page_num": 1,
      "total_pages": 312,
      "method": "native",
      "native_chars": 1847,
      "final_chars": 1923,
      "columns_detected": 1,
      "tables_found": 0,
      "links_found": 3,
      "images_found": 1,
      "images_ocrd": 1,
      "footnotes_found": 2,
      "header_footer_lines_removed": 2,
      "ocr_lines": 0,
      "ocr_avg_confidence": 0.0,
      "ocr_min_confidence": 0.0,
      "ocr_lines_dropped": 0,
      "warnings": [],
      "error": null
    },
    {
      "page_num": 45,
      "total_pages": 312,
      "method": "ocr",
      "native_chars": 12,
      "final_chars": 834,
      "columns_detected": 1,
      "tables_found": 0,
      "links_found": 0,
      "images_found": 0,
      "images_ocrd": 0,
      "footnotes_found": 0,
      "header_footer_lines_removed": 0,
      "ocr_lines": 47,
      "ocr_avg_confidence": 0.8934,
      "ocr_min_confidence": 0.6102,
      "ocr_lines_dropped": 3,
      "warnings": ["low output: only 42 chars"],
      "error": null
    }
  ]
}
```

### PageReport Fields

| Field | Type | Description |
|---|---|---|
| `page_num` | int | Page number (1-based) |
| `method` | str | `native` / `ocr` / `hybrid` / `failed` |
| `native_chars` | int | Characters from native PDF text layer |
| `final_chars` | int | Total characters after all processing stages |
| `columns_detected` | int | Number of columns detected |
| `tables_found` | int | Number of tables on page |
| `links_found` | int | Number of hyperlinks on page |
| `images_found` | int | Number of embedded images |
| `images_ocrd` | int | Number of images that underwent OCR |
| `footnotes_found` | int | Number of footnotes detected |
| `header_footer_lines_removed` | int | Number of header/footer lines removed |
| `ocr_lines` | int | Number of lines accepted from OCR |
| `ocr_avg_confidence` | float | Average OCR confidence score (0.0–1.0) |
| `ocr_min_confidence` | float | Minimum OCR confidence on page |
| `ocr_lines_dropped` | int | Lines dropped due to low confidence |
| `warnings` | list | Non-critical warnings |
| `error` | str\|null | Critical page error |

### Handling `low_quality_pages`

Pages with `final_chars < 50`. Options:

1. Review manually — might be blank or illustration pages (acceptable)
2. Reprocess with `--dpi 350` to improve OCR
3. Exclude from training if page is truly empty

---

## `train.jsonl` — Fine-Tuning Dataset

Each line is a JSON object with one chunk of text.

### Format

```jsonl
{"text": "Chapter 1. Network Security Fundamentals\n\nNetwork security is..."}
{"text": "...continued. The TCP/IP protocol provides...\n\n[TABLE]\n| Layer | Protocol |\n..."}
{"text": "SQL Injection — a database attack through..."}
```

### Framework Compatibility

| Framework | Compatibility | Note |
|---|---|---|
| Unsloth | Native | `{"text": "..."}` — standard format |
| LLaMA-Factory | Native | Dataset type: `pretraining` |
| Axolotl | Native | `type: completion` |
| HuggingFace Trainer | Native | `text` field read directly |
| TRL SFTTrainer | Native | `dataset_text_field="text"` |

### Loading in Python

```python
import json
from datasets import Dataset

data = [json.loads(line) for line in open("extracted/train.jsonl", encoding="utf-8")]
dataset = Dataset.from_list(data)
```

---

## `extraction_report.json` — Summary Report

Aggregated statistics across all processed PDFs.

### Example

```json
{
  "generated_at": "2026-04-22T10:45:00+00:00",
  "pdf_dir": "C:/Books",
  "total_pdfs": 10,
  "total_chunks": 8453,
  "total_warnings": 23,
  "total_errors": 0,
  "settings": {
    "chunk": 1024,
    "overlap": 64,
    "lang": "en",
    "dpi": 250,
    "conf": 0.6,
    "no_ocr": false
  },
  "pdfs": [ ... array of PDFManifest objects ... ]
}
```

### What to Check After Run

1. `total_errors == 0` — no critical errors
2. `total_warnings` — small number is normal, large number → check log
3. Review `pdfs[*].low_quality_pages` — if many low-quality pages, try `--dpi 350`
4. `pdfs[*].pages_failed == 0` — all pages loaded successfully

---

## `health_report.txt` — Quality Report (Quality Control)

Analyzes OCR confidence and identifies problematic PDFs.

### Example

```
======================================================================
QUALITY CONTROL REPORT
======================================================================

CRITICAL ISSUES (must fix before training):
──────────────────────────────────────────────────────────────────────
  X book_with_low_ocr.pdf
    Avg confidence: 0.42 (should be >= 0.70)
    Low quality pages: 45/120 (37.5%)
    Problem pages: [15, 23, 45, 67, 89, ...]
    Recommendation: CRITICAL: 37.5% pages low quality. Try: --dpi 350 --conf 0.4 or --no-ocr

WARNINGS (consider filtering or re-processing):
──────────────────────────────────────────────────────────────────────
  ! book_with_issues.pdf
    Avg confidence: 0.63
    Low quality: 18%
    Action: WARNING: 18% pages low quality. Consider: --dpi 300 --conf 0.5

GOOD PDFs (ready for training):
──────────────────────────────────────────────────────────────────────
  8/10 PDFs passed quality check

AUTO-GENERATED REPAIR RECIPES:
──────────────────────────────────────────────────────────────────────
  book_with_low_ocr.pdf:
    python batch_extract.py '<pdf_dir>/book_with_low_ocr.pdf' --dpi 350 --conf 0.4 --reprocess
    OR: python batch_extract.py '<pdf_dir>/book_with_low_ocr.pdf' --no-ocr --reprocess

======================================================================
SUMMARY: 8 good, 1 warnings, 1 critical
======================================================================
```

---

## `train.lowquality.jsonl` — Low-Quality Chunks

If problematic PDFs are found (critical/warning), their chunks are separated into a file for manual review.

**Schema**: identical to `train.jsonl`, but contains only chunks from low-OCR-confidence or low-character-count pages.

**Usage:**
```bash
# Review quality manually
head -20 extracted/train.lowquality.jsonl

# If acceptable — add to main dataset
cat extracted/train.lowquality.jsonl >> extracted/train.jsonl

# If not acceptable — discard
rm extracted/train.lowquality.jsonl
```

---

## `.extraction_blacklist.json` — Corrupted PDFs List

Created automatically if script crashes. Contains names of PDFs that caused errors.

### Example

```json
["corrupted_book.pdf", "empty_scan.pdf"]
```

### Behavior on Next Run

- These PDFs are automatically skipped (message: `[N/M] file.pdf (skipped - repeated failure)`)
- Processing continues with next file

### Manual Recovery

Edit the file manually or use recovery mode:

```bash
# Reprocess blacklisted PDFs (if problem was temporary)
rm extracted/.extraction_blacklist.json

# Or reprocess a single PDF
python batch_extract.py 'C:/Books/corrupted_book.pdf' --reprocess

# Rebuild datasets without blacklist
python batch_extract.py --exclude-blacklist
```

---

## `extraction.log` — Complete Operation Log

Log with timestamps. Levels: INFO, WARNING, ERROR.

```
2026-04-22 10:30:01 INFO Found 10 PDF(s)
2026-04-22 10:30:01 INFO Loading PaddleOCR (lang=en)…
2026-04-22 10:30:15 INFO [1/10] Hacking_Art_Exploitation.pdf
2026-04-22 10:30:15 INFO   Detecting headers/footers…
2026-04-22 10:30:16 INFO   Repeated header/footer patterns: 4
2026-04-22 10:32:44 INFO   pages=312 | chars=847,293 | tables=34 | links=127 | warnings=3 | errors=0 | low_q=2
2026-04-22 10:32:44 WARNING   Low-quality pages: [45, 178]
2026-04-22 10:32:44 ERROR  QUALITY: CRITICAL: 37.5% pages low quality. Try: --dpi 350 --conf 0.4 or --no-ocr
2026-04-22 10:32:44 INFO   847 chunks written
```
