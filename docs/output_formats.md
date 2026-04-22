# Форматы выходных файлов

---

## `<stem>.txt` — Текст документа

Полный извлечённый текст одного PDF. UTF-8, структурированный.

### Структура

```
[BookName:PAGE 1/312 | NATIVE]
<текст первой страницы>

[TABLE]
| Колонка 1 | Колонка 2 |
|-----------|-----------|
| Данные    | Данные    |
[/TABLE]

[BookName:PAGE 2/312 | OCR]
<текст распознанной страницы>

[IMAGE_OCR]
<текст из встроенной картинки>
[/IMAGE_OCR]

[FOOTNOTES]
  * Текст сноски
[/FOOTNOTES]

[LINKS]
  [1] https://example.com
[/LINKS]
```

### Маркеры

| Маркер | Что означает |
|---|---|
| `[PDFName:PAGE N/TOTAL \| METHOD]` | Начало страницы. Включает имя PDF-файла для идентификации при фильтрации качества. METHOD: NATIVE / OCR / HYBRID / FAILED |
| `[TABLE]...[/TABLE]` | Таблица в markdown-формате |
| `[IMAGE_OCR]...[/IMAGE_OCR]` | Текст, извлечённый из встроенного изображения |
| `[FOOTNOTES]...[/FOOTNOTES]` | Сноски страницы (собраны из нижней части) |
| `[LINKS]...[/LINKS]` | Гиперссылки страницы |
| `[NO TEXT]` | Страница без извлечённого контента (отмечается для аудита) |

---

## `<stem>.manifest.json` — Отчёт по документу

Детальный JSON-отчёт по каждой странице каждого PDF. Создаётся одновременно с `.txt`.

### Пример

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

### Поля `PageReport`

| Поле | Тип | Описание |
|---|---|---|
| `page_num` | int | Номер страницы (1-based) |
| `method` | str | `native` / `ocr` / `hybrid` / `failed` |
| `native_chars` | int | Символов из нативного PDF-слоя |
| `final_chars` | int | Итоговое кол-во символов после всех стадий |
| `columns_detected` | int | Кол-во обнаруженных колонок |
| `tables_found` | int | Таблиц на странице |
| `links_found` | int | Гиперссылок на странице |
| `images_found` | int | Встроенных изображений |
| `images_ocrd` | int | Изображений, для которых запустился OCR |
| `footnotes_found` | int | Обнаруженных сносок |
| `header_footer_lines_removed` | int | Удалённых строк колонтитулов |
| `ocr_lines` | int | Строк, принятых от OCR |
| `ocr_avg_confidence` | float | Средний confidence OCR (0.0–1.0) |
| `ocr_min_confidence` | float | Минимальный confidence OCR |
| `ocr_lines_dropped` | int | Строк, отброшенных из-за низкого confidence |
| `warnings` | list | Предупреждения (не критичные) |
| `error` | str\|null | Критическая ошибка страницы |

### Что делать с `low_quality_pages`

Страницы с `final_chars < 50`. Варианты:

1. Проверить вручную — возможно это пустые или иллюстративные страницы (норм)
2. Повторить с `--dpi 350` для улучшения OCR
3. Исключить из обучения если страница действительно пустая

---

## `train.jsonl` — Датасет для файн-тюнинга

Каждая строка — JSON-объект с одним чанком текста.

### Формат

```jsonl
{"text": "Глава 1. Основы сетевой безопасности\n\nСетевая безопасность — это..."}
{"text": "...продолжение. Протокол TCP/IP обеспечивает...\n\n[TABLE]\n| Уровень | Протокол |\n..."}
{"text": "SQL-инъекция (SQL Injection) — атака на базу данных через..."}
```

### Совместимость с фреймворками

| Фреймворк | Совместимость | Примечание |
|---|---|---|
| Unsloth | Нативная | `{"text": "..."}` — стандартный формат |
| LLaMA-Factory | Нативная | Тип датасета: `pretraining` |
| Axolotl | Нативная | `type: completion` |
| HuggingFace Trainer | Нативная | Поле `text` читается напрямую |
| TRL SFTTrainer | Нативная | `dataset_text_field="text"` |

### Загрузка в Python

```python
import json
from datasets import Dataset

data = [json.loads(line) for line in open("extracted/train.jsonl", encoding="utf-8")]
dataset = Dataset.from_list(data)
```

---

## `extraction_report.json` — Сводный отчёт

Агрегированная статистика по всем обработанным PDF.

### Пример

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
    "lang": "ru",
    "dpi": 250,
    "conf": 0.6,
    "no_ocr": false
  },
  "pdfs": [ ... массив PDFManifest ... ]
}
```

### Что проверять после запуска

1. `total_errors == 0` — нет критических ошибок
2. `total_warnings` — небольшое число нормально, большое число — стоит проверить лог
3. Пройдись по `pdfs[*].low_quality_pages` — если много страниц с низким качеством, попробуй `--dpi 350`
4. `pdfs[*].pages_failed == 0` — все страницы загрузились

---

## `health_report.txt` — Отчёт качества (Quality Control)

Анализирует OCR-confidence и идентифицирует проблемные PDF.

### Пример

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

## `train.lowquality.jsonl` — Чанки из проблемных страниц

Если обнаружены проблемные PDF (critical/warning), чанки из них отделяются в отдельный файл для ручного просмотра.

**Схема:** идентична `train.jsonl`, но содержит только чанки со страниц с низким OCR-confidence или низким объёмом текста.

**Использование:**
```bash
# Проверить качество вручную
head -20 extracted/train.lowquality.jsonl

# Если устраивает — добавить в основной датасет
cat extracted/train.lowquality.jsonl >> extracted/train.jsonl

# Если не устраивает — удалить
rm extracted/train.lowquality.jsonl
```

---

## `.extraction_blacklist.json` — Список повреждённых PDF

Создаётся автоматически при краше скрипта. Содержит имена PDF-файлов, которые вызвали ошибки.

### Пример

```json
["corrupted_book.pdf", "empty_scan.pdf"]
```

### Поведение при следующем запуске

- Эти PDF автоматически пропускаются (сообщение `[N/M] file.pdf (skipped - repeated failure)`)
- Обработка продолжается со следующего файла

### Ручной ремонт

Отредактируй файл вручную или используй режим восстановления:

```bash
# Переобработать исключённые PDF (если проблема была временной)
rm extracted/.extraction_blacklist.json

# Или просто переобработать один PDF
python batch_extract.py 'extracted/corrupted_book.pdf' --reprocess

# Перестроить датасеты без чёрного списка
python batch_extract.py --exclude-blacklist
```

---

## `extraction.log` — Полный лог

Лог с временными метками. Уровни: INFO, WARNING, ERROR.

```
2026-04-22 10:30:01 INFO Found 10 PDF(s)
2026-04-22 10:30:01 INFO Loading PaddleOCR (lang=ru)…
2026-04-22 10:30:15 INFO [1/10] Haking_Iskusstvo_eksployta.pdf
2026-04-22 10:30:15 INFO   Detecting headers/footers…
2026-04-22 10:30:16 INFO   Repeated header/footer patterns: 4
2026-04-22 10:32:44 INFO   pages=312 | chars=847,293 | tables=34 | links=127 | warnings=3 | errors=0 | low_q=2
2026-04-22 10:32:44 WARNING   Low-quality pages: [45, 178]
2026-04-22 10:32:44 ERROR  QUALITY: CRITICAL: 37.5% pages low quality. Try: --dpi 350 --conf 0.4 or --no-ocr
2026-04-22 10:32:44 INFO   847 chunks written
```
