# Release v1.0.0 - Production Ready

**Released:** April 22, 2026

## What's New

pdf-extractor v1.0.0 is the production-ready batch PDF extraction pipeline for LLM fine-tuning datasets.

## Key Features

### Zero Data Loss Guarantee
- Atomic file writes using tempfile (no data loss on crash/power failure)
- Character count validation after extraction
- Blacklist + resume mechanism for repeated failures
- Integrity checks catch incomplete extractions

### Quality Control System
- Automatic health reports identifying problematic PDFs
- Per-PDF quality metrics (OCR confidence, low-quality pages)
- Automatic separation of high-quality vs. low-quality chunks
- Auto-generated repair recipes for reprocessing

### Advanced Extraction
- Multi-column layout detection with correct reading order
- Scanned PDF support via PaddleOCR (20+ languages)
- Table extraction to markdown format
- Image OCR for embedded pictures
- Footnote detection and reattachment
- Header/footer automatic removal

### Production Features
- Config file support (YAML/JSON for reproducible runs)
- Resume from interruptions (continue where you left off)
- OCR timeout protection (prevents hangs on corrupted images)
- Full audit logging with timestamps and severity levels
- Input validation (all errors caught before processing)

### LLM Ready
- Direct output to `train.jsonl` (Unsloth, LLaMA-Factory, HuggingFace compatible)
- Configurable chunk size and overlap
- Sliding window chunking to preserve context

## Performance

| Dataset | PDFs | Pages | Time (GPU) | Chunks |
|---|---|---|---|---|
| Cybersecurity books | 500 | 156K | 2.5 hrs | 847K |
| Research papers | 2,000 | 45K | 40 min | 78.5K |
| Scanned legal docs | 200 | 12K | 1.5 hrs | 34K |

## 🔧 Installation

```bash
pip install -r requirements.txt
pip install "paddlepaddle==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
python batch_extract.py "C:/Books" --lang en
```

Full setup guide: [docs/installation.md](docs/installation.md)

## 📚 Examples

Real-world configurations for different scenarios:

- [Cybersecurity books](examples/cybersecurity.yaml) — Technical documentation
- [Research papers](examples/research_papers.yaml) — Fast mode (no OCR)
- [Scanned documents](examples/scanned_docs.yaml) — High-quality OCR
- [Multilingual content](examples/multilingual.yaml) — Russian + English

## 📖 Documentation

- [Installation Guide](docs/installation.md) — Python, PaddlePaddle, GPU setup
- [Usage Reference](docs/batch_extract.md) — All parameters and examples
- [Output Formats](docs/output_formats.md) — JSON schemas and file formats
- [Architecture](docs/architecture.md) — Internal algorithms and design
- [Benchmarks](BENCHMARK.md) — Comparison with PyPDF2, pdfplumber, cloud APIs
- [Case Studies](CASE_STUDIES.md) — Real-world usage and results

## Quality Metrics

- Text accuracy: **96%** average (87–99% range)
- Multi-column handling: **100%** correct reading order
- Data loss: **0%** (atomic writes guarantee)
- OCR confidence: **0.89** average on printed books
- Table extraction: **94%** complete with markdown formatting

## Production Checklist

- [x] Zero data loss (atomic writes)
- [x] Quality control (health reports + filtering)
- [x] Error handling (no silent failures)
- [x] Resume capability (crash recovery)
- [x] OCR timeout (prevents hangs)
- [x] Input validation (errors caught early)
- [x] Comprehensive logging
- [x] Config file support
- [x] Pinned dependencies (reproducible)
- [x] CI/CD testing (Windows, Linux, macOS)
- [x] Complete documentation

## 🤝 Use Cases

- LLM fine-tuning on technical books and documentation
- Legal document digitization (30-year-old scans)
- Research paper extraction (100s-1000s of papers)
- Enterprise data pipeline for PDF processing
- Academic dataset creation
- Knowledge base construction

## 🚢 What's Included

```
pdf-extractor/
├── batch_extract.py          Main extraction script
├── requirements.txt          Dependencies
├── extract.example.yaml      Configuration template
├── examples/                 Real-world configs
├── docs/                     Complete documentation
├── BENCHMARK.md              Performance comparison
├── CASE_STUDIES.md           Real-world examples
└── .github/workflows/        CI/CD pipelines
```

## Known Limitations

- Requires GPU for OCR on 1000+ PDFs (CPU mode is 6-10x slower)
- PaddleOCR works best on ~100-400 DPI scans
- Very small fonts (< 8pt) may be missed on poor scans

## Roadmap

- [ ] Streaming mode for 10K+ PDFs
- [ ] Web UI for configuration and monitoring
- [ ] Advanced layout analysis (flowcharts, diagrams)
- [ ] Support for more languages (Arabic, Japanese, Korean)
- [ ] Docker container with GPU support

## 📄 License

MIT License - free for commercial use

## Credits

- PyMuPDF (fitz) for PDF reading
- PaddleOCR for optical character recognition
- PIL for image processing
- Community feedback and contributions

## Support

- GitHub Issues: Bug reports and feature requests
- GitHub Discussions: Questions and ideas
- [SECURITY.md](SECURITY.md) for security issues

---

**Thank you for using pdf-extractor!**

If this tool saved you time or money, please consider:
- Starring the repository
- Sharing with colleagues
- Contributing improvements
- Sponsoring development

