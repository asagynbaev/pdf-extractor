# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-22

### Added
- **Production-grade PDF extraction** with support for text, tables, images, and hyperlinks
- **Quality Control System** with automatic health reports and low-quality chunk filtering
- **Multi-column layout detection** for correct text ordering in multi-column documents
- **Automatic header/footer removal** with frequency-based detection
- **Cross-page paragraph merging** to handle text split across page boundaries
- **Footnote detection and reattachment** using font size analysis
- **Table extraction as Markdown** with automatic formatting
- **Embedded image OCR** using PaddleOCR with confidence scoring
- **Full-page OCR** for scanned PDFs with configurable DPI
- **Atomic file writes** preventing data loss on crashes
- **OCR timeout mechanism** to prevent hanging on corrupted images
- **Integrity validation** with character count matching and page failure detection
- **Resume and blacklist mechanism** for crash recovery and repeated failure handling
- **YAML/JSON configuration file support** for reproducible runs
- **Comprehensive logging** with timestamps and severity levels
- **Zero silent failures** - all errors are logged and reported
- **Pinned dependencies** for reproducibility across environments
- **Complete documentation** with installation, usage, architecture, and output format guides
- **GitHub integration** with issue templates and contribution guidelines
- **PyPI packaging** with proper metadata for package discovery

### Features
- Batch processing of hundreds of PDFs
- Ready-to-use training data for LLM fine-tuning (Unsloth, LLaMA-Factory, HuggingFace)
- CPU and GPU support (NVIDIA CUDA)
- Windows, Linux, and macOS compatibility
- Configurable chunk size and overlap for optimal training data
- Multiple OCR language support (Russian, English, Chinese, etc.)
- Automatic quality filtering with separate datasets for manual review

### Documentation
- Quick start guide (30 seconds to first run)
- Installation guide for Windows/Linux with CPU/GPU options
- Full parameter reference with examples
- Output format specification with JSON schemas
- Internal architecture documentation
- Contributing guidelines
- MIT License

## Future Roadmap

- [ ] GPU acceleration for OCR
- [ ] Support for more OCR languages
- [ ] Web UI for configuration and monitoring
- [ ] Cloud deployment options
- [ ] Real-time processing pipeline
- [ ] Integration with popular ML frameworks

---

For detailed information about each release, see the [releases page](https://github.com/yourusername/pdf-extractor/releases).
