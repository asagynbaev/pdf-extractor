# Архитектура

Внутреннее устройство `batch_extract.py` — как именно работает каждый компонент.

---

## Общий поток данных

```
PDF файл
    │
    ▼
sha256_file()          ← контрольная сумма для идентификации
    │
    ▼
detect_header_footer_strings()
    │  Проходит по ВСЕМ страницам один раз
    │  Собирает первые и последние 2 блока каждой страницы
    │  Строки, встречающиеся на ≥ 40% страниц → повторяющиеся
    │  Страницы с меняющимися числами ("Глава 3 — 42") нормализуются:
    │  цифры заменяются на "#" перед сравнением
    │
    ▼
Для каждой страницы:
    │
    ├─ extract_page()
    │       │
    │       ├─ _extract_links()          page.get_links() → {rect: uri}
    │       │
    │       ├─ _detect_footnotes()       page.get_text("dict") → размеры шрифтов
    │       │   Находит блоки в нижних 25% страницы с шрифтом < 85% от основного
    │       │
    │       ├─ page.find_tables()        PyMuPDF встроенный детектор таблиц
    │       │   └─ _table_to_markdown()  → markdown с fallback на plain cells
    │       │
    │       ├─ page.get_text("blocks")   Все текстовые блоки с координатами
    │       │   ├─ Пропуск блоков сносок (по индексу из _detect_footnotes)
    │       │   ├─ Пропуск блоков внутри таблиц (пересечение rect)
    │       │   ├─ Пропуск колонтитулов (_is_header_footer)
    │       │   └─ _assign_columns()     Кластеризация по x-центру блоков
    │       │       Сортировка: (col_index, y) — колонка-первый, потом сверху вниз
    │       │
    │       ├─ Встроенные изображения    page.get_images(full=True)
    │       │   ├─ Фильтрация по W×H    (img-min-px)
    │       │   ├─ _bytes_to_rgb()       PIL декодинг
    │       │   └─ ocr_engine.predict()  → _parse_ocr_result() с фильтром confidence
    │       │
    │       ├─ Полностраничный OCR       если native_chars < min-native
    │       │   ├─ page.get_pixmap()     рендер в DPI
    │       │   ├─ _pix_to_rgb()
    │       │   └─ ocr_engine.predict()  → _parse_ocr_result()
    │       │
    │       └─ Сборка: text + tables + image_ocr + footnotes + links
    │
    ├─ _merge_cross_page_paragraphs()
    │   Если конец стр. N не заканчивается на . ! ? и
    │   начало стр. N+1 — маленькая буква → склеить
    │
    └─ Сохранение .txt и .manifest.json
    
chunk_text()            Скользящее окно по словам
    │
    ▼
train.jsonl             {"text": "..."} — одна запись = один чанк
```

---

## Компоненты

### `PageReport` и `PDFManifest`

Python dataclasses. Сериализуются через `dataclasses.asdict()` в JSON без потери полей. Ни одно значение не теряется — все счётчики инкрементируются явно.

### `detect_header_footer_strings(doc)`

```python
# Нормализация: "Глава 3 — 42" → "глава # — #"
def _normalise(s): return re.sub(r"\b\d+\b", "#", s.strip().lower())

# Порог: 40% страниц должны иметь эту строку
threshold = max(2, int(n * 0.40))
```

Проверяет первые 2 и последние 2 текстовых блока каждой страницы. Это покрывает 99% книжных колонтитулов не захватывая контент.

### `_assign_columns(blocks, page_width)`

Алгоритм:
1. Вычисляет x-центр каждого блока: `(x0 + x1) / 2`
2. Сортирует все уникальные x-центры
3. Ищет пробелы между соседними центрами > 15% ширины страницы
4. Каждый пробел = граница колонки
5. Присваивает блокам индекс колонки, сортирует по `(col_index, y0)`

Пример для двухколоночной страницы (ширина 595pt):
```
Блоки с x-центром 120–150pt → колонка 0
Пробел ~250pt (> 595 * 0.15 = 89pt) → граница
Блоки с x-центром 380–420pt → колонка 1
Результат: все блоки кол.0 читаются до блоков кол.1
```

### `_detect_footnotes(page)`

1. Получает `page.get_text("dict")` — детальный формат с размерами шрифтов
2. Находит самый частый размер шрифта = основной текст
3. Блоки в нижних 25% страницы с шрифтом < 85% от основного → сноски
4. Возвращает индексы блоков для исключения из основного текста

### `_parse_ocr_result(items, conf_threshold)`

PaddleOCR возвращает список prediction-объектов. У каждого:
- `rec_texts` — список строк
- `rec_scores` — соответствующие confidence scores (0.0–1.0)

Строки с `score < conf_threshold` отбрасываются и считаются в `ocr_lines_dropped`. Это критически важно для скан-страниц плохого качества — без фильтрации OCR мусор попадает в датасет.

### `_merge_cross_page_paragraphs(pages_text)`

```python
_SENTENCE_END = re.compile(r'[.!?…»"''")\]>]\s*$')  # конец предложения
_STARTS_LOWER = re.compile(r'^\s*[а-яёa-z]')         # маленькая буква

# Если предыдущая страница НЕ заканчивается на знак препинания
# И текущая начинается с маленькой буквы → склеить
```

Обрабатывает случай когда PDF-ридер разбивает абзац ровно на границе страницы.

### `chunk_text(text, chunk_size, overlap)`

Скользящее окно по словам (не токенам, не символам):

```
words = text.split()
для i в диапазоне(0, len(words), chunk_size - overlap):
    chunk = words[i : i + chunk_size]
```

Перекрытие (`overlap=64`) гарантирует что контекст на границах чанков не теряется при обучении.

---

## Обработка ошибок

Каждая операция завёрнута в `try/except`:

| Уровень | Поведение при ошибке |
|---|---|
| `fitz.open()` | PDF пропускается, ошибка в manifest и лог |
| `load_page()` | Страница помечается `method=failed`, обработка продолжается |
| `find_tables()` | Предупреждение, таблицы пропускаются, текст извлекается |
| `extract_image()` | Предупреждение, картинка пропускается |
| `ocr_engine.predict()` | Предупреждение, OCR пропускается |
| Весь PDF | Критическая ошибка, PDF пропускается, остальные обрабатываются |

Ни одна ошибка не прерывает обработку всей очереди. Всё фиксируется.

---

## Quality Control System

После извлечения всех PDF автоматически запускается система контроля качества:

### `compute_quality_metrics(manifest: dict) -> QualityMetrics`

Анализирует manifest каждого PDF и вычисляет:
- `avg_confidence` — средний confidence score OCR-блоков (0.0–1.0)
- `min_confidence` — минимальный confidence в PDF
- `pages_low_confidence` — список страниц с confidence < 0.70
- `pages_very_low_quality` — список страниц с < 50 символов (пустые/повреждённые)
- `issue_severity` — "ok" | "warning" | "critical"

Правила severity:
- **CRITICAL**: avg_conf < 0.50 ИЛИ > 30% страниц низкого качества
- **WARNING**: avg_conf < 0.65 ИЛИ > 15% страниц низкого качества
- **OK**: всё хорошо

### `generate_health_report(metrics_list, out_path) -> str`

Генерирует текстовый отчёт со следующими секциями:

1. **CRITICAL ISSUES** — PDFs которые нужно переоработать
2. **WARNINGS** — PDFs которые можно отфильтровать
3. **GOOD PDFs** — готовые к обучению
4. **AUTO-GENERATED REPAIR RECIPES** — команды для переобработки

Пример рецепта ремонта для Book1.pdf с низким confidence:
```bash
python batch_extract.py '<pdf_dir>/Book1.pdf' --dpi 350 --conf 0.4 --reprocess
```

### `filter_low_quality_chunks(jsonl_in, manifests, quality_metrics, out_dir) -> tuple[int, int]`

Разделяет train.jsonl на две части:

1. **train.jsonl** — чанки только с хорошими страниц
2. **train.lowquality.jsonl** — чанки с проблемных страниц для ручного просмотра

Идентификация: каждый чанк содержит page header типа `[book_name:PAGE 5/100 | OCR]`. Функция проверяет есть ли такие page markers в чанке для проблемных страниц.

---

## Зависимости и их роли

```
fitz (PyMuPDF)
  ├─ fitz.open()           — открытие PDF
  ├─ page.get_text()       — нативный текст в разных форматах
  ├─ page.find_tables()    — обнаружение и извлечение таблиц
  ├─ page.get_images()     — список встроенных изображений
  ├─ doc.extract_image()   — байты изображения по xref
  ├─ page.get_links()      — гиперссылки
  ├─ page.get_pixmap()     — рендер страницы в растр
  └─ fitz.Pixmap           — операции с растровым изображением

paddleocr.PaddleOCR
  └─ .predict(np.ndarray)  — OCR изображения

PIL.Image (pillow)
  └─ Image.open()          — декодирование встроенных изображений

numpy
  └─ np.frombuffer()       — конвертация pixmap байтов в массив
```
