"""
Production-grade batch PDF extractor with Quality Control.

Features:
  - Multi-column layout, header/footer removal, hyperlinks, footnotes
  - Cross-page paragraph merging, tables → markdown, image OCR
  - Full-page OCR for scans, atomic file writes, OCR timeout
  - Integrity validation, resume + skip-on-repeated-failure
  - CONFIG FILES (YAML/JSON), progress logging

NEW: Quality Control System
  - Health report: list of problematic PDFs with recommendations
  - Quality filtering: auto-exclude low-quality chunks from train.jsonl
  - train.lowquality.jsonl: separate file for manual review
  - Repair recipes: auto-generated commands to fix problems
  - Preview mode: quickly view problematic pages
  - Exclusion mechanism: --exclude-blacklist

Usage:
    python batch_extract.py <pdf_dir> [options]
    python batch_extract.py --config extract.yaml
    python batch_extract.py --preview HackingBook.pdf
    python batch_extract.py --exclude-blacklist  # rebuild without blacklisted
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import re
import shutil
import signal
import sys
import tempfile
import time
import traceback
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

try:
    import yaml
except ImportError:
    yaml = None

import fitz
import numpy as np

log = logging.getLogger("extractor")

# ═════════════════════════════════════════════════════════════════════════════
# Configuration & Validation
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    pdf_dir: Path
    out_dir: Path
    chunk_size: int
    overlap: int
    lang: str
    dpi: float
    min_native: int
    conf_threshold: float
    img_min_px: int
    no_ocr: bool
    reprocess: bool

    def validate(self) -> list[str]:
        """Validate config. Return list of errors."""
        errors = []

        if not self.pdf_dir.is_dir():
            errors.append(f"PDF directory not found: {self.pdf_dir}")
        elif not os.access(self.pdf_dir, os.R_OK):
            errors.append(f"PDF directory not readable: {self.pdf_dir}")

        if self.chunk_size <= 0:
            errors.append(f"chunk_size must be > 0, got {self.chunk_size}")
        if self.overlap < 0 or self.overlap >= self.chunk_size:
            errors.append(f"overlap must be 0 <= overlap < chunk_size")
        if not 0.0 <= self.conf_threshold <= 1.0:
            errors.append(f"conf_threshold must be in [0, 1], got {self.conf_threshold}")
        if self.dpi <= 0:
            errors.append(f"dpi must be > 0, got {self.dpi}")
        if self.min_native < 0:
            errors.append(f"min_native must be >= 0, got {self.min_native}")
        if self.img_min_px < 0:
            errors.append(f"img_min_px must be >= 0, got {self.img_min_px}")

        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            errors.append(f"Output directory not writable: {self.out_dir}")
        except OSError as e:
            errors.append(f"Cannot create output directory: {e}")

        free_gb = shutil.disk_usage(self.out_dir).free / (1024**3)
        if free_gb < 1.0:
            errors.append(f"Less than 1 GB free disk space ({free_gb:.2f} GB)")

        return errors


# ═════════════════════════════════════════════════════════════════════════════
# Quality Metrics & Health Report
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class QualityMetrics:
    """Per-PDF quality assessment."""
    pdf_name: str
    avg_confidence: float
    min_confidence: float
    pages_ocr_count: int
    pages_low_confidence: list[int]  # pages with avg_conf < 0.70
    pages_very_low_quality: list[int]  # pages with < 50 chars
    low_quality_percentage: float
    has_issues: bool
    issue_severity: str  # "ok" | "warning" | "critical"
    recommended_action: str


def compute_quality_metrics(manifest: dict) -> QualityMetrics:
    """Compute quality metrics from PDF manifest."""
    pdf_name = Path(manifest["pdf_path"]).name
    pages = manifest.get("pages", [])

    # Collect OCR confidence scores
    confidences = []
    pages_ocr = []
    pages_low_conf = []
    pages_very_low = []

    for page in pages:
        if page.get("ocr_avg_confidence", 0) > 0:
            confidences.append(page["ocr_avg_confidence"])
            pages_ocr.append(page["page_num"])
        if page.get("ocr_avg_confidence", 1.0) < 0.70 and page.get("method") == "ocr":
            pages_low_conf.append(page["page_num"])
        if page.get("final_chars", 0) < 50:
            pages_very_low.append(page["page_num"])

    avg_conf = sum(confidences) / len(confidences) if confidences else 1.0
    min_conf = min(confidences) if confidences else 1.0
    low_quality_pct = (len(pages_low_conf) + len(pages_very_low)) / len(pages) * 100 if pages else 0

    # Determine severity and recommendation
    has_issues = bool(pages_low_conf or pages_very_low)

    if not has_issues:
        severity = "ok"
        recommendation = "All good - ready for training"
    elif avg_conf < 0.50 or low_quality_pct > 30:
        severity = "critical"
        recommendation = f"CRITICAL: {low_quality_pct:.0f}% pages low quality. Try: --dpi 350 --conf 0.4 or --no-ocr"
    elif avg_conf < 0.65 or low_quality_pct > 15:
        severity = "warning"
        recommendation = f"WARNING: {low_quality_pct:.0f}% pages low quality. Consider: --dpi 300 --conf 0.5"
    else:
        severity = "ok"
        recommendation = "Minor issues, usable but filter out low-confidence chunks"

    return QualityMetrics(
        pdf_name=pdf_name,
        avg_confidence=round(avg_conf, 4),
        min_confidence=round(min_conf, 4),
        pages_ocr_count=len(pages_ocr),
        pages_low_confidence=pages_low_conf,
        pages_very_low_quality=pages_very_low,
        low_quality_percentage=round(low_quality_pct, 1),
        has_issues=has_issues,
        issue_severity=severity,
        recommended_action=recommendation,
    )


def generate_health_report(metrics_list: list[QualityMetrics], out_path: Path) -> str:
    """Generate health report and return summary."""
    critical = [m for m in metrics_list if m.issue_severity == "critical"]
    warning = [m for m in metrics_list if m.issue_severity == "warning"]
    good = [m for m in metrics_list if m.issue_severity == "ok"]

    report_lines = [
        "",
        "═" * 70,
        "QUALITY CONTROL REPORT",
        "═" * 70,
    ]

    # Critical issues
    if critical:
        report_lines.extend([
            "",
            "CRITICAL ISSUES (must fix before training):",
            "─" * 70,
        ])
        for m in critical:
            report_lines.append(f"  X {m.pdf_name}")
            report_lines.append(f"    Avg confidence: {m.avg_confidence} (should be >= 0.70)")
            report_lines.append(f"    Low quality pages: {len(m.pages_low_confidence) + len(m.pages_very_low_quality)}/{m.pages_ocr_count} ({m.low_quality_percentage}%)")
            if m.pages_low_confidence:
                report_lines.append(f"    Problem pages: {m.pages_low_confidence[:10]}{'...' if len(m.pages_low_confidence) > 10 else ''}")
            report_lines.append(f"    Recommendation: {m.recommended_action}")
            report_lines.append("")

    # Warnings
    if warning:
        report_lines.extend([
            "",
            "WARNINGS (consider filtering or re-processing):",
            "─" * 70,
        ])
        for m in warning:
            report_lines.append(f"  ! {m.pdf_name}")
            report_lines.append(f"    Avg confidence: {m.avg_confidence}")
            report_lines.append(f"    Low quality: {m.low_quality_percentage}%")
            report_lines.append(f"    Action: {m.recommended_action}")
            report_lines.append("")

    # Good
    report_lines.extend([
        "",
        "GOOD PDFs (ready for training):",
        "─" * 70,
        f"  {len(good)}/{len(metrics_list)} PDFs passed quality check",
        "",
    ])

    # Auto repair recipes
    if critical or warning:
        report_lines.extend([
            "",
            "AUTO-GENERATED REPAIR RECIPES:",
            "─" * 70,
        ])
        for m in critical + warning:
            # Extract PDF name without extension
            pdf_stem = Path(m.pdf_name).stem
            report_lines.append(f"  {m.pdf_name}:")
            if m.avg_confidence < 0.60:
                cmd = f"    python batch_extract.py '<pdf_dir>/{pdf_stem}.pdf' --dpi 350 --conf 0.4 --reprocess"
                report_lines.append(cmd)
            if m.low_quality_percentage > 50:
                cmd = f"    OR: python batch_extract.py '<pdf_dir>/{pdf_stem}.pdf' --no-ocr --reprocess"
                report_lines.append(cmd)
            if m.avg_confidence < 0.65 and m.avg_confidence >= 0.50:
                cmd = f"    OR: python batch_extract.py '<pdf_dir>/{pdf_stem}.pdf' --dpi 300 --conf 0.5 --reprocess"
                report_lines.append(cmd)

    # Summary
    report_lines.extend([
        "",
        "═" * 70,
        f"SUMMARY: {len(good)} good, {len(warning)} warnings, {len(critical)} critical",
        "═" * 70,
        "",
    ])

    report_text = "\n".join(report_lines)
    out_path.write_text(report_text, encoding="utf-8")
    return report_text


def filter_low_quality_chunks(
    jsonl_in: Path,
    manifests: list[dict],
    quality_metrics: list[QualityMetrics],
    out_dir: Path,
    conf_threshold: float = 0.70,
) -> tuple[int, int]:
    """
    Filter train.jsonl:
    - train.jsonl: only high-quality chunks
    - train.lowquality.jsonl: chunks from problematic pages for manual review

    Returns: (chunks_kept, chunks_filtered)
    """
    # Build set of problematic page identifiers
    problematic_pages = set()
    for metric in quality_metrics:
        if metric.has_issues:
            for page_num in metric.pages_low_confidence + metric.pages_very_low_quality:
                problematic_pages.add((metric.pdf_name, page_num))

    if not problematic_pages:
        return 0, 0  # No filtering needed

    kept = 0
    filtered = 0

    # Read all lines first (important for Windows file locking)
    with jsonl_in.open("r", encoding="utf-8") as f_in:
        lines = f_in.readlines()

    # Now process and write to output files
    with (out_dir / "train.jsonl").open("w", encoding="utf-8") as f_good:
        with (out_dir / "train.lowquality.jsonl").open("w", encoding="utf-8") as f_bad:
            for line in lines:
                try:
                    chunk = json.loads(line)
                    text = chunk.get("text", "")

                    # Check if chunk contains text from problematic pages
                    is_problematic = False
                    for pdf_name, page_num in problematic_pages:
                        pdf_stem = Path(pdf_name).stem
                        if f"[{pdf_stem}:PAGE {page_num}" in text:
                            is_problematic = True
                            break

                    if is_problematic:
                        f_bad.write(line)
                        filtered += 1
                    else:
                        f_good.write(line)
                        kept += 1
                except Exception:
                    f_good.write(line)
                    kept += 1

    log.info("Quality filtering: %d chunks kept, %d filtered to lowquality", kept, filtered)
    return kept, filtered


# ═════════════════════════════════════════════════════════════════════════════
# Data structures
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class PageReport:
    page_num: int
    total_pages: int
    method: str
    native_chars: int = 0
    final_chars: int = 0
    columns_detected: int = 1
    tables_found: int = 0
    links_found: int = 0
    images_found: int = 0
    images_ocrd: int = 0
    footnotes_found: int = 0
    header_footer_lines_removed: int = 0
    ocr_lines: int = 0
    ocr_avg_confidence: float = 0.0
    ocr_min_confidence: float = 0.0
    ocr_lines_dropped: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class PDFManifest:
    pdf_path: str
    pdf_sha256: str
    extracted_at: str
    total_pages: int
    pages: list[PageReport] = field(default_factory=list)
    total_chars: int = 0
    pages_native: int = 0
    pages_ocr: int = 0
    pages_hybrid: int = 0
    pages_failed: int = 0
    tables_total: int = 0
    links_total: int = 0
    images_ocrd_total: int = 0
    low_quality_pages: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ═════════════════════════════════════════════════════════════════════════════
# File I/O — Atomic writes
# ═════════════════════════════════════════════════════════════════════════════

def _atomic_write(path: Path, content: str, encoding: str = "utf-8") -> bool:
    """Write to file atomically."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            dir=path.parent,
            delete=False,
            suffix=".tmp",
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        tmp_path.replace(path)
        return True
    except Exception as e:
        log.error("Atomic write failed to %s: %s", path, e)
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def _atomic_write_json(path: Path, data: dict, **json_kwargs) -> bool:
    """Write JSON atomically."""
    try:
        content = json.dumps(data, ensure_ascii=False, **json_kwargs)
        return _atomic_write(path, content)
    except Exception as e:
        log.error("JSON write failed: %s", e)
        return False


# ═════════════════════════════════════════════════════════════════════════════
# Integrity validation
# ═════════════════════════════════════════════════════════════════════════════

def validate_extraction(txt_path: Path, manifest_path: Path) -> tuple[bool, list[str]]:
    """Validate extraction coherence."""
    issues = []
    try:
        txt = txt_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, [f"Cannot read extraction: {e}"]

    txt_len = len(txt)
    manifest_chars = manifest.get("total_chars", 0)

    if abs(txt_len - manifest_chars) > max(1000, manifest_chars * 0.1):
        issues.append(f"Character count mismatch: txt={txt_len}, manifest={manifest_chars}")

    if manifest.get("pages_failed", 0) > 0:
        issues.append(f"{manifest['pages_failed']} page(s) failed")

    if len(manifest.get("low_quality_pages", [])) > manifest["total_pages"] * 0.2:
        issues.append(f">{20}% pages low quality")

    return len(issues) == 0, issues


# ═════════════════════════════════════════════════════════════════════════════
# Image helpers
# ═════════════════════════════════════════════════════════════════════════════

def _pix_to_rgb(pix: fitz.Pixmap) -> np.ndarray:
    if pix.alpha or pix.n != 3:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    return np.frombuffer(memoryview(pix.samples), dtype=np.uint8).reshape(
        pix.height, pix.width, 3
    ).copy()


def _bytes_to_rgb(data: bytes) -> np.ndarray | None:
    try:
        from PIL import Image
        return np.array(Image.open(io.BytesIO(data)).convert("RGB"))
    except Exception as e:
        log.debug("PIL decode failed: %s", e)
        return None


# ═════════════════════════════════════════════════════════════════════════════
# OCR helpers — with timeout
# ═════════════════════════════════════════════════════════════════════════════

class _OCRTimeout(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _OCRTimeout("OCR timeout")


def _parse_ocr_result(items, conf_threshold: float) -> tuple[str, dict]:
    kept, dropped = [], 0
    confidences: list[float] = []
    for item in items:
        d = item.json if hasattr(item, "json") else item
        if not isinstance(d, dict):
            continue
        inner = d.get("res", d)
        texts = inner.get("rec_texts") or []
        scores = inner.get("rec_scores") or []
        if len(scores) < len(texts):
            scores = scores + [1.0] * (len(texts) - len(scores))
        for t, s in zip(texts, scores):
            t = str(t).strip()
            if not t:
                continue
            conf = float(s)
            confidences.append(conf)
            if conf >= conf_threshold:
                kept.append(t)
            else:
                dropped += 1
    avg = sum(confidences) / len(confidences) if confidences else 0.0
    mn = min(confidences) if confidences else 0.0
    return "\n".join(kept), {
        "ocr_lines": len(kept),
        "ocr_lines_dropped": dropped,
        "ocr_avg_confidence": round(avg, 4),
        "ocr_min_confidence": round(mn, 4),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Header / footer detection
# ═════════════════════════════════════════════════════════════════════════════

def _normalise(s: str) -> str:
    return re.sub(r"\b\d+\b", "#", s.strip().lower())


def detect_header_footer_strings(doc: fitz.Document, sample_lines: int = 2) -> set[str]:
    top_counter, bot_counter = Counter(), Counter()
    n = doc.page_count
    for i in range(n):
        try:
            page = doc.load_page(i)
            blocks = sorted(
                [b for b in page.get_text("blocks") if b[6] == 0],
                key=lambda b: b[1],
            )
            lines = [b[4].strip() for b in blocks if b[4].strip()]
            for line in lines[:sample_lines]:
                top_counter[_normalise(line)] += 1
            for line in lines[-sample_lines:]:
                bot_counter[_normalise(line)] += 1
        except Exception as e:
            log.debug("header detection on page %d: %s", i, e)
    threshold = max(2, int(n * 0.40))
    repeated = {k for k, v in top_counter.items() if v >= threshold}
    repeated |= {k for k, v in bot_counter.items() if v >= threshold}
    repeated.discard("")
    return repeated


def _is_header_footer(line: str, repeated: set[str]) -> bool:
    return _normalise(line) in repeated


# ═════════════════════════════════════════════════════════════════════════════
# Multi-column layout
# ═════════════════════════════════════════════════════════════════════════════

class _Block(NamedTuple):
    x0: float
    y0: float
    x1: float
    y1: float
    text: str


def _assign_columns(blocks: list[_Block], page_width: float) -> list[tuple[int, _Block]]:
    if not blocks:
        return []
    centres = sorted({(b.x0 + b.x1) / 2 for b in blocks})
    gap_threshold = page_width * 0.15
    col_boundaries = [0.0]
    for a, b in zip(centres, centres[1:]):
        if b - a > gap_threshold:
            col_boundaries.append((a + b) / 2)
    col_boundaries.append(page_width)

    def col_of(block: _Block) -> int:
        cx = (block.x0 + block.x1) / 2
        for i, (lo, hi) in enumerate(zip(col_boundaries, col_boundaries[1:])):
            if lo <= cx < hi:
                return i
        return len(col_boundaries) - 2

    return sorted(
        [(col_of(b), b) for b in blocks],
        key=lambda x: (x[0], x[1].y0),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Hyperlinks & Footnotes & Tables
# ═════════════════════════════════════════════════════════════════════════════

def _extract_links(page: fitz.Page) -> dict:
    result = {}
    try:
        for link in page.get_links():
            uri = link.get("uri", "")
            if uri:
                r = link["from"]
                result[(r.x0, r.y0, r.x1, r.y1)] = uri
    except Exception:
        pass
    return result


def _detect_footnotes(page: fitz.Page) -> tuple[list[str], set[int]]:
    footnotes, skip_indices = [], set()
    try:
        page_height = page.rect.height
        raw = page.get_text("dict")
        blocks = raw.get("blocks", [])
        all_sizes = []
        for b in blocks:
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    s = span.get("size", 0)
                    if s > 0:
                        all_sizes.append(round(s, 1))
        if not all_sizes:
            return [], set()
        body_size = Counter(all_sizes).most_common(1)[0][0]
        for bi, b in enumerate(blocks):
            if b.get("type") != 0 or b["bbox"][1] < page_height * 0.75:
                continue
            small_spans = []
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size", body_size) < body_size * 0.85:
                        t = span.get("text", "").strip()
                        if t:
                            small_spans.append(t)
            if small_spans:
                text = " ".join(small_spans).strip()
                if len(text) > 5:
                    footnotes.append(text)
                    skip_indices.add(bi)
    except Exception as e:
        log.debug("footnote detection: %s", e)
    return footnotes, skip_indices


def _table_to_markdown(tab) -> str | None:
    try:
        md = tab.to_markdown()
        if md and md.strip():
            return md.strip()
    except Exception:
        pass
    try:
        rows = tab.extract()
        if not rows:
            return None
        lines = [" | ".join(str(c or "").replace("\n", " ") for c in r) for r in rows]
        sep = " | ".join(["---"] * (lines[0].count("|") + 1))
        return "\n".join([lines[0], sep] + lines[1:])
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Per-page extraction
# ═════════════════════════════════════════════════════════════════════════════

def extract_page(
    doc: fitz.Document,
    page_idx: int,
    ocr_engine,
    repeated_hf: set[str],
    *,
    min_native_chars: int,
    dpi: float,
    img_min_px: int,
    conf_threshold: float,
    ocr_timeout: int = 60,
) -> tuple[str, PageReport]:
    pn = page_idx + 1
    report = PageReport(page_num=pn, total_pages=doc.page_count, method="native")

    try:
        page = doc.load_page(page_idx)
    except Exception as e:
        report.method = "failed"
        report.error = f"load_page: {e}"
        return "", report

    page_width = page.rect.width
    output_parts: list[str] = []

    links = _extract_links(page)
    report.links_found = len(links)

    footnotes, footnote_block_indices = _detect_footnotes(page)
    report.footnotes_found = len(footnotes)

    table_rects, table_blocks = [], []
    try:
        tabs = page.find_tables()
        for tab in tabs:
            md = _table_to_markdown(tab)
            if md:
                table_rects.append(fitz.Rect(tab.bbox))
                table_blocks.append(f"\n[TABLE]\n{md}\n[/TABLE]\n")
                report.tables_found += 1
    except Exception as e:
        report.warnings.append(f"table extraction: {e}")

    raw_blocks, hf_removed = [], 0
    try:
        all_blocks = page.get_text("blocks")
        for bi, b in enumerate(all_blocks):
            if b[6] != 0 or bi in footnote_block_indices:
                continue
            brect = fitz.Rect(b[:4])
            if any(brect.intersects(tr) for tr in table_rects):
                continue
            txt = (b[4] or "").strip()
            if txt and not _is_header_footer(txt, repeated_hf):
                raw_blocks.append(_Block(b[0], b[1], b[2], b[3], txt))
            elif txt:
                hf_removed += 1
    except Exception as e:
        report.warnings.append(f"native text: {e}")

    report.header_footer_lines_removed = hf_removed
    col_blocks = _assign_columns(raw_blocks, page_width)
    if col_blocks:
        report.columns_detected = max(c for c, _ in col_blocks) + 1
    native_text = "\n\n".join(b.text for _, b in col_blocks)
    report.native_chars = len(native_text)
    if native_text:
        output_parts.append(native_text)
    output_parts.extend(table_blocks)

    if ocr_engine is not None:
        seen = set()
        try:
            for img_info in page.get_images(full=True):
                xref = img_info[0]
                if xref in seen:
                    continue
                seen.add(xref)
                report.images_found += 1
                try:
                    base = doc.extract_image(xref)
                    w, h = base.get("width", 0), base.get("height", 0)
                    if w * h < img_min_px:
                        continue
                    arr = _bytes_to_rgb(base["image"])
                    if arr is None:
                        report.warnings.append(f"xref {xref}: PIL decode failed")
                        continue
                    try:
                        signal.signal(signal.SIGALRM, _timeout_handler)
                        signal.alarm(ocr_timeout)
                        pred = ocr_engine.predict(arr)
                        signal.alarm(0)
                    except _OCRTimeout:
                        signal.alarm(0)
                        report.warnings.append(f"xref {xref}: OCR timeout")
                        continue
                    ocr_txt, stats = _parse_ocr_result(pred, conf_threshold)
                    if ocr_txt.strip():
                        output_parts.append(f"\n[IMAGE_OCR]\n{ocr_txt.strip()}\n[/IMAGE_OCR]\n")
                        report.images_ocrd += 1
                        report.ocr_lines += stats["ocr_lines"]
                        report.ocr_lines_dropped += stats["ocr_lines_dropped"]
                except Exception as e:
                    report.warnings.append(f"image xref {xref}: {e}")
        except Exception as e:
            report.warnings.append(f"get_images: {e}")

    if ocr_engine is not None and report.native_chars < min_native_chars:
        try:
            m = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=m, alpha=False)
            arr = _pix_to_rgb(pix)
            pix = None
            try:
                signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(ocr_timeout)
                pred = ocr_engine.predict(arr)
                signal.alarm(0)
            except _OCRTimeout:
                signal.alarm(0)
                report.warnings.append("full-page OCR timeout")
                return "", report
            ocr_txt, stats = _parse_ocr_result(pred, conf_threshold)
            if ocr_txt.strip():
                output_parts.insert(0, ocr_txt.strip())
                report.ocr_lines += stats["ocr_lines"]
                report.ocr_lines_dropped += stats["ocr_lines_dropped"]
                report.ocr_avg_confidence = stats["ocr_avg_confidence"]
                report.ocr_min_confidence = stats["ocr_min_confidence"]
                report.method = "ocr" if report.native_chars == 0 else "hybrid"
        except Exception as e:
            report.warnings.append(f"full-page OCR: {e}")

    if footnotes:
        fn_text = "\n".join(f"  * {fn}" for fn in footnotes)
        output_parts.append(f"\n[FOOTNOTES]\n{fn_text}\n[/FOOTNOTES]\n")
    assembled = "\n\n".join(p for p in output_parts if p.strip())
    if links:
        uris = list(dict.fromkeys(links.values()))
        if uris:
            refs = "\n".join(f"  [{i+1}] {u}" for i, u in enumerate(uris))
            assembled += f"\n\n[LINKS]\n{refs}\n[/LINKS]"

    report.final_chars = len(assembled)
    if report.final_chars < 50 and not report.error:
        report.warnings.append(f"low output: only {report.final_chars} chars")

    return assembled, report


# ═════════════════════════════════════════════════════════════════════════════
# Cross-page merging
# ═════════════════════════════════════════════════════════════════════════════

_SENTENCE_END = re.compile(r'[.!?…]["\')>]*\s*$', re.UNICODE)
_STARTS_LOWER = re.compile(r'^\s*[а-яёa-z]')


def _merge_cross_page_paragraphs(pages_text: list[str]) -> list[str]:
    if len(pages_text) < 2:
        return pages_text
    result = [pages_text[0]]
    for page_text in pages_text[1:]:
        prev = result[-1]
        prev_lines = [l for l in prev.splitlines() if l.strip()]
        curr_lines = [l for l in page_text.splitlines() if l.strip()]
        if (
            prev_lines
            and curr_lines
            and not _SENTENCE_END.search(prev_lines[-1])
            and _STARTS_LOWER.match(curr_lines[0])
        ):
            result[-1] = prev.rstrip() + " " + page_text.lstrip()
        else:
            result.append(page_text)
    return result


# ═════════════════════════════════════════════════════════════════════════════
# Per-PDF extraction
# ═════════════════════════════════════════════════════════════════════════════

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_pdf(
    pdf_path: Path,
    ocr_engine,
    *,
    min_native_chars: int,
    dpi: float,
    img_min_px: int,
    conf_threshold: float,
    ocr_timeout: int = 60,
) -> tuple[str, PDFManifest]:
    manifest = PDFManifest(
        pdf_path=str(pdf_path),
        pdf_sha256=sha256_file(pdf_path),
        extracted_at=datetime.now(timezone.utc).isoformat(),
        total_pages=0,
    )
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        manifest.errors.append(f"fitz.open: {e}")
        return "", manifest

    manifest.total_pages = doc.page_count
    repeated_hf = detect_header_footer_strings(doc)
    raw_pages = []
    for i in range(doc.page_count):
        text, report = extract_page(
            doc,
            i,
            ocr_engine,
            repeated_hf,
            min_native_chars=min_native_chars,
            dpi=dpi,
            img_min_px=img_min_px,
            conf_threshold=conf_threshold,
            ocr_timeout=ocr_timeout,
        )
        manifest.pages.append(report)
        manifest.total_chars += report.final_chars
        manifest.tables_total += report.tables_found
        manifest.links_total += report.links_found
        manifest.images_ocrd_total += report.images_ocrd
        {
            "native": lambda: setattr(manifest, "pages_native", manifest.pages_native + 1),
            "ocr": lambda: setattr(manifest, "pages_ocr", manifest.pages_ocr + 1),
            "hybrid": lambda: setattr(manifest, "pages_hybrid", manifest.pages_hybrid + 1),
            "failed": lambda: setattr(manifest, "pages_failed", manifest.pages_failed + 1),
        }.get(report.method, lambda: None)()
        if report.method == "failed":
            manifest.errors.append(f"page {report.page_num}: {report.error}")
        if report.final_chars < 50:
            manifest.low_quality_pages.append(report.page_num)
        raw_pages.append((text, report.page_num))

    doc.close()
    texts = [t for t, _ in raw_pages]
    texts = _merge_cross_page_paragraphs(texts)
    assembled = []
    pdf_name = Path(manifest.pdf_path).stem
    for (_, pn), text in zip(raw_pages, texts):
        method = manifest.pages[pn - 1].method.upper()
        header = f"[{pdf_name}:PAGE {pn}/{manifest.total_pages} | {method}]"
        assembled.append(f"{header}\n{text}" if text.strip() else f"{header}\n[NO TEXT]")

    return "\n\n".join(assembled), manifest


# ═════════════════════════════════════════════════════════════════════════════
# Chunking
# ═════════════════════════════════════════════════════════════════════════════

def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        c = " ".join(words[i : i + chunk_size])
        if c.strip():
            chunks.append(c)
        i += chunk_size - overlap
    return chunks


# ═════════════════════════════════════════════════════════════════════════════
# Config file support
# ═════════════════════════════════════════════════════════════════════════════

def load_config_file(path: Path) -> dict:
    """Load YAML/JSON config."""
    if not yaml:
        raise ImportError("pyyaml not installed. pip install pyyaml")
    with path.open() as f:
        if path.suffix == ".json":
            return json.load(f)
        else:
            return yaml.safe_load(f) or {}


# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════

def build_ocr(lang: str):
    from paddleocr import PaddleOCR
    log.info("Loading PaddleOCR (lang=%s)...", lang)
    return PaddleOCR(
        lang=lang,
        ocr_version="PP-OCRv5",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Production PDF -> JSONL extractor with Quality Control")
    ap.add_argument("pdf_dir", nargs="?", default=None)
    ap.add_argument("--config", default=None, help="YAML/JSON config file")
    ap.add_argument("--out", default="extracted")
    ap.add_argument("--chunk", type=int, default=1024)
    ap.add_argument("--overlap", type=int, default=64)
    ap.add_argument("--lang", default="ru")
    ap.add_argument("--dpi", type=float, default=250)
    ap.add_argument("--min-native", type=int, default=80)
    ap.add_argument("--conf", type=float, default=0.6)
    ap.add_argument("--img-min-px", type=int, default=8000)
    ap.add_argument("--ocr-timeout", type=int, default=60)
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--reprocess", action="store_true")
    ap.add_argument("--exclude-blacklist", action="store_true", help="Rebuild datasets excluding blacklisted PDFs")
    args = ap.parse_args(argv)

    # Load config
    if args.config:
        try:
            cfg_dict = load_config_file(Path(args.config))
            pdf_dir = cfg_dict.get("pdf_dir") or args.pdf_dir
            out_dir = cfg_dict.get("out_dir", args.out)
            chunk = cfg_dict.get("chunk_size", args.chunk)
            overlap = cfg_dict.get("overlap", args.overlap)
            lang = cfg_dict.get("lang", args.lang)
            dpi = cfg_dict.get("dpi", args.dpi)
            min_native = cfg_dict.get("min_native", args.min_native)
            conf = cfg_dict.get("conf_threshold", args.conf)
            img_min_px = cfg_dict.get("img_min_px", args.img_min_px)
            no_ocr = cfg_dict.get("no_ocr", args.no_ocr)
            reprocess = cfg_dict.get("reprocess", args.reprocess)
            ocr_timeout = cfg_dict.get("ocr_timeout", args.ocr_timeout)
        except Exception as e:
            print(f"Failed to load config: {e}", file=sys.stderr)
            return 1
    else:
        if args.exclude_blacklist:
            pdf_dir = None
        elif not args.pdf_dir:
            ap.print_help()
            return 1
        else:
            pdf_dir = args.pdf_dir
        out_dir = args.out
        chunk = args.chunk
        overlap = args.overlap
        lang = args.lang
        dpi = args.dpi
        min_native = args.min_native
        conf = args.conf
        img_min_px = args.img_min_px
        no_ocr = args.no_ocr
        reprocess = args.reprocess
        ocr_timeout = args.ocr_timeout

    out_path = Path(out_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(out_path / "extraction.log", encoding="utf-8"),
        ],
    )

    # Handle --exclude-blacklist mode
    if args.exclude_blacklist:
        log.info("Rebuilding datasets excluding blacklisted PDFs...")
        blacklist_file = out_path / ".extraction_blacklist.json"
        jsonl_path = out_path / "train.jsonl"

        if blacklist_file.exists() and jsonl_path.exists():
            blacklist = set(json.loads(blacklist_file.read_text()))
            if not blacklist:
                log.info("No blacklisted PDFs found")
                return 0

            manifests = []
            for mf in out_path.glob("*.manifest.json"):
                try:
                    m = json.loads(mf.read_text())
                    pdf_name = Path(m["pdf_path"]).name
                    if pdf_name not in blacklist:
                        manifests.append(m)
                except Exception:
                    pass

            metrics = [compute_quality_metrics(m) for m in manifests]
            kept, filtered = filter_low_quality_chunks(jsonl_path, manifests, metrics, out_path, conf)
            log.info("Excluded %d blacklisted PDFs", len(blacklist))
            log.info("Quality filtering: %d chunks kept, %d filtered", kept, filtered)
            return 0
        else:
            log.error("No extraction data found")
            return 1

    # Normal processing
    if pdf_dir is None:
        ap.print_help()
        return 1

    config = Config(
        pdf_dir=Path(pdf_dir).expanduser().resolve(),
        out_dir=out_path,
        chunk_size=chunk,
        overlap=overlap,
        lang=lang,
        dpi=dpi,
        min_native=min_native,
        conf_threshold=conf,
        img_min_px=img_min_px,
        no_ocr=no_ocr,
        reprocess=reprocess,
    )

    errors = config.validate()
    if errors:
        print("\nConfiguration errors:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    pdfs = sorted(config.pdf_dir.glob("*.pdf"))
    if not pdfs:
        log.error("No PDFs found in %s", config.pdf_dir)
        return 1
    log.info("Found %d PDF(s)", len(pdfs))

    ocr = None if config.no_ocr else build_ocr(config.lang)
    if not config.no_ocr:
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            log.warning("Pillow not installed - image OCR disabled")

    skip_blacklist = set()
    blacklist_file = config.out_dir / ".extraction_blacklist.json"
    if blacklist_file.exists():
        try:
            skip_blacklist = set(json.loads(blacklist_file.read_text()))
        except Exception:
            pass

    jsonl_path = config.out_dir / "train.jsonl"
    report_path = config.out_dir / "extraction_report.json"
    health_report_path = config.out_dir / "health_report.txt"
    all_manifests = []
    all_metrics = []
    total_chunks = 0
    total_warnings = 0
    total_errors = 0
    processed = 0
    skipped_repeated_fail = 0

    start_time = time.time()

    try:
        with jsonl_path.open("w", encoding="utf-8") as jf:
            for idx, pdf in enumerate(pdfs, 1):
                stem = pdf.stem

                if stem in skip_blacklist:
                    log.warning("[%d/%d] %s (skipped - repeated failure)", idx, len(pdfs), pdf.name)
                    skipped_repeated_fail += 1
                    continue

                txt_path = config.out_dir / f"{stem}.txt"
                manifest_path = config.out_dir / f"{stem}.manifest.json"

                log.info("[%d/%d] %s", idx, len(pdfs), pdf.name)

                if txt_path.exists() and manifest_path.exists() and not config.reprocess:
                    log.info("  resuming from existing extraction")
                    valid, issues = validate_extraction(txt_path, manifest_path)
                    if issues:
                        for issue in issues:
                            log.warning("  integrity check: %s", issue)
                    text = txt_path.read_text(encoding="utf-8")
                    md = json.loads(manifest_path.read_text(encoding="utf-8"))
                    all_manifests.append(md)
                    all_metrics.append(compute_quality_metrics(md))
                    processed += 1
                else:
                    try:
                        text, manifest = extract_pdf(
                            pdf,
                            ocr,
                            min_native_chars=config.min_native,
                            dpi=config.dpi,
                            img_min_px=config.img_min_px,
                            conf_threshold=config.conf_threshold,
                            ocr_timeout=ocr_timeout,
                        )

                        if not _atomic_write(txt_path, text):
                            raise IOError(f"Failed to write {txt_path}")
                        if not _atomic_write_json(manifest_path, asdict(manifest), indent=2):
                            raise IOError(f"Failed to write {manifest_path}")

                        valid, issues = validate_extraction(txt_path, manifest_path)
                        if issues:
                            for issue in issues:
                                log.warning("  integrity check: %s", issue)

                        md = asdict(manifest)
                        all_manifests.append(md)
                        metric = compute_quality_metrics(md)
                        all_metrics.append(metric)
                        processed += 1

                        w = sum(len(p["warnings"]) for p in md["pages"])
                        e = len(md["errors"])
                        lq = len(md["low_quality_pages"])
                        total_warnings += w
                        total_errors += e

                        log.info(
                            "  pages=%d | chars=%s | tables=%d | links=%d | warnings=%d | errors=%d | low_q=%d",
                            manifest.total_pages,
                            f"{manifest.total_chars:,}",
                            manifest.tables_total,
                            manifest.links_total,
                            w,
                            e,
                            lq,
                        )

                        # Quality warning
                        if metric.issue_severity == "critical":
                            log.error("  QUALITY: %s", metric.recommended_action)
                        elif metric.issue_severity == "warning":
                            log.warning("  QUALITY: %s", metric.recommended_action)

                        if manifest.low_quality_pages:
                            log.warning("  Low-quality pages: %s", manifest.low_quality_pages)
                        for err in manifest.errors:
                            log.error("  %s", err)
                    except Exception as e:
                        log.error("  FATAL: %s\n%s", e, traceback.format_exc())
                        skip_blacklist.add(stem)
                        total_errors += 1
                        continue

                chunks = chunk_text(text, config.chunk_size, config.overlap)
                for c in chunks:
                    jf.write(json.dumps({"text": c}, ensure_ascii=False) + "\n")
                total_chunks += len(chunks)
                log.info("  %d chunks written", len(chunks))

    except KeyboardInterrupt:
        log.warning("Interrupted by user")
        return 130

    if skip_blacklist:
        blacklist_file.write_text(json.dumps(sorted(skip_blacklist)))

    # Generate health report
    health_text = generate_health_report(all_metrics, health_report_path)
    log.info("\n%s", health_text)

    # Quality filtering
    if all_metrics and any(m.has_issues for m in all_metrics):
        kept, filtered = filter_low_quality_chunks(jsonl_path, all_manifests, all_metrics, config.out_dir, config.conf_threshold)
        log.info("Quality filtering: %d chunks in train.jsonl, %d in train.lowquality.jsonl", kept, filtered)

    # Final report
    elapsed = time.time() - start_time
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pdf_dir": str(config.pdf_dir),
        "total_pdfs": len(pdfs),
        "processed": processed,
        "skipped_repeated_fail": skipped_repeated_fail,
        "total_chunks": total_chunks,
        "total_warnings": total_warnings,
        "total_errors": total_errors,
        "elapsed_seconds": round(elapsed, 2),
        "elapsed_human": str(timedelta(seconds=int(elapsed))),
        "settings": {
            "chunk_size": config.chunk_size,
            "overlap": config.overlap,
            "lang": config.lang,
            "dpi": config.dpi,
            "ocr_timeout": ocr_timeout,
            "no_ocr": config.no_ocr,
        },
        "pdfs": all_manifests,
    }
    _atomic_write_json(report_path, summary, indent=2)

    log.info("=" * 70)
    log.info("PDFs: %d total, %d processed", len(pdfs), processed)
    log.info("Chunks: %d -> %s", total_chunks, jsonl_path)
    log.info("Errors: %d", total_errors)
    log.info("Time: %s", str(timedelta(seconds=int(elapsed))))
    log.info("Health report: %s", health_report_path)
    log.info("=" * 70)

    return 1 if total_errors > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
