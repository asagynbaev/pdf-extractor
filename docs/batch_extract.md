# batch_extract.py — Complete Reference

Main script for batch PDF processing → `train.jsonl`.

---

## Syntax

```bash
# Direct execution
python batch_extract.py <pdf_dir> [options]

# Using config file
python batch_extract.py --config extract.yaml
```

---

## Arguments

### Positional

| Argument | Description |
|---|---|
| `pdf_dir` | Path to folder with PDFs (optional if using `--config`) |

### Optional Flags

| Flag | Default | Description |
|---|---|---|
| `--config PATH` | — | YAML/JSON config file (overrides all CLI flags) |
| `--out DIR` | `extracted` | Output directory for results |
| `--chunk INT` | `1024` | Chunk size in words |
| `--overlap INT` | `64` | Overlap between chunks (words) |
| `--lang STR` | `en` | PaddleOCR language: `en`, `ru`, `zh`, etc |
| `--dpi FLOAT` | `250` | DPI for full-page OCR rendering |
| `--min-native INT` | `80` | Min characters to skip OCR |
| `--conf FLOAT` | `0.6` | OCR confidence threshold (0.0–1.0) |
| `--img-min-px INT` | `8000` | Min image size (W×H pixels) for OCR |
| `--ocr-timeout INT` | `60` | OCR timeout in seconds (prevents hangs) |
| `--no-ocr` | off | Skip OCR (text + tables only) |
| `--reprocess` | off | Reprocess even if .txt exists |
| `--exclude-blacklist` | — | Rebuild datasets excluding blacklisted PDFs |

---

## Usage Examples

### Basic

```bash
python batch_extract.py "C:/Books"
```

### Fast (text only, no OCR)

```bash
python batch_extract.py "C:/Books" --no-ocr
```

### High quality (for poor scans)

```bash
python batch_extract.py "C:/Books" --dpi 350 --conf 0.5
```

### Using config file

```bash
python batch_extract.py --config extract.yaml
```

### Quality Control — Exclude Problematic PDFs

If processing was interrupted and `.extraction_blacklist.json` was created:

```bash
# Rebuild datasets, skipping corrupted PDFs
python batch_extract.py --exclude-blacklist
```

This rebuilds `train.jsonl` and `train.lowquality.jsonl` excluding the blacklist.

---

## Configuration File (YAML)

Create `extract.yaml`:

```yaml
pdf_dir: C:/Books/Cybersecurity
out_dir: ./extracted
chunk_size: 1024
overlap: 64
lang: en
dpi: 250
min_native: 80
conf_threshold: 0.6
img_min_px: 8000
ocr_timeout: 60
no_ocr: false
reprocess: false
```

Run:

```bash
python batch_extract.py --config extract.yaml
```

Convenient for repeated runs with same parameters.

---

## Production Features

### Input Validation

```
ERROR: PDF directory not found: C:/NonExistent
ERROR: chunk_size must be > 0, got -1
ERROR: Output directory not writable: /root/protected
ERROR: Less than 1 GB free disk space (0.50 GB)
```

All errors are shown BEFORE processing starts.

### Atomic Operations

If the process crashes:
- `.txt` file is written to temporary file → renamed atomically
- `.manifest.json` is written the same way
- Data is never lost on crash or power failure

### OCR Timeout

If OCR hangs on an image:

```
--ocr-timeout 60    # usually 60 sec is enough
--ocr-timeout 120   # for slow CPU or GPU
```

Without timeout, a page can hang forever. With timeout, the page is skipped and processing continues.

### Skip on Repeated Failure

If PDF #7 always causes a crash:
- First crash → added to `.extraction_blacklist.json`
- Next run → automatically skipped

You can manually edit `.extraction_blacklist.json` to reprocess.

### Integrity Validation

After each PDF, the script checks:
- Does `.txt` length match `total_chars` in manifest (±10%)?
- Are there pages with `failed` status?
- Are there too many `low_quality_pages`?

```
integrity check: Character count mismatch: txt=847293, manifest=845200
integrity check: 2 page(s) failed to extract
```

### Resume + Reprocess

```bash
# First run — processes all PDFs
python batch_extract.py "C:/Books"

# Second run — skips completed, continues interrupted
python batch_extract.py "C:/Books"

# Reprocess everything from scratch
python batch_extract.py "C:/Books" --reprocess
```

---

## Output Files

| File | Description |
|---|---|
| `<stem>.txt` | Full extracted text |
| `<stem>.manifest.json` | Per-page extraction report |
| `train.jsonl` | All chunks from all PDFs |
| `extraction_report.json` | Summary: time, speed, errors |
| `extraction.log` | Complete operation log with timestamps |
| `.extraction_blacklist.json` | List of PDFs with repeated errors |

---

## Output Interpretation

```
[1/100] Book1.pdf
  resuming from existing extraction
  pages=312 | chars=847,293 | tables=34 | links=127 | warnings=3 | errors=0 | low_q=2
  Low-quality pages: [45, 178]
  847 chunks written

[2/100] Book2.pdf
  Detecting headers/footers…
  Repeated header/footer patterns: 4
  pages=298 | chars=756,184 | tables=28 | links=94 | warnings=1 | errors=0 | low_q=0
  782 chunks written

...

═════════════════════════════════════════════════════════════════════════════
PDFs         : 100 total, 99 processed
Total chunks : 84530  →  extracted/train.jsonl
Total errors : 0
Time elapsed : 1:32:45
Report       : extracted/extraction_report.json
═════════════════════════════════════════════════════════════════════════════
```

| Metric | Good | Problem |
|---|---|---|
| `errors=0` | Yes | Bad if > 0 |
| `warnings` | 0–5 per PDF | Many warnings → check log |
| `low_q` | 0–2 per PDF | > 5% of pages → reprocess with `--dpi 350` |
| `chars` | Hundreds of thousands | < 10K → likely empty or bad PDF |

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success, no errors |
| `1` | Completed with errors |
| `130` | Interrupted by user (Ctrl+C) |
