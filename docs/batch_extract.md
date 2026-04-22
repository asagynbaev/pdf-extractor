# batch_extract.py — Полный справочник

Основной скрипт для батч-обработки PDF → `train.jsonl`.

---

## Синтаксис

```bash
# Прямой запуск
python batch_extract.py <pdf_dir> [опции]

# Через конфиг
python batch_extract.py --config extract.yaml
```

---

## Аргументы

### Позиционный

| Аргумент | Описание |
|---|---|
| `pdf_dir` | Путь к папке с PDF (опционально если использовать `--config`) |

### Опциональные

| Флаг | Умолчание | Описание |
|---|---|---|
| `--config PATH` | — | YAML/JSON конфиг файл (переопределяет все CLI флаги) |
| `--out DIR` | `extracted` | Папка для результатов |
| `--chunk INT` | `1024` | Размер чанка в словах |
| `--overlap INT` | `64` | Перекрытие между чанками (слова) |
| `--lang STR` | `ru` | PaddleOCR язык: `ru`, `en`, `cyrillic`, `ch` |
| `--dpi FLOAT` | `250` | DPI рендеринга для полностраничного OCR |
| `--min-native INT` | `80` | Символов на странице чтобы пропустить OCR |
| `--conf FLOAT` | `0.6` | Min confidence для OCR (0.0–1.0) |
| `--img-min-px INT` | `8000` | Min площадь картинки W×H для OCR |
| `--ocr-timeout INT` | `60` | Timeout OCR в секундах (предотвращает зависания) |
| `--no-ocr` | выкл | Только текст + таблицы, без OCR |
| `--reprocess` | выкл | Переобработать даже если .txt существует |

---

## Примеры запуска

### Базовый

```bash
python batch_extract.py "C:/Books"
```

### Быстро (только текст, без OCR)

```bash
python batch_extract.py "C:/Books" --no-ocr
```

### Высокое качество (для плохих сканов)

```bash
python batch_extract.py "C:/Books" --dpi 350 --conf 0.5
```

### С конфиг-файлом

```bash
python batch_extract.py --config extract.yaml
```

### Quality Control — исключить проблемные PDF

Если обработка была прервана и появился `.extraction_blacklist.json`:

```bash
# Перестроить датасеты, пропуская повреждённые PDF
python batch_extract.py --exclude-blacklist
```

Это переделает `train.jsonl` и `train.lowquality.jsonl` исключив чёрный список.

---

## Конфиг файл (YAML)

Создай `extract.yaml`:

```yaml
pdf_dir: C:/Books/Cybersecurity
out_dir: ./extracted
chunk_size: 1024
overlap: 64
lang: ru
dpi: 250
min_native: 80
conf_threshold: 0.6
img_min_px: 8000
ocr_timeout: 60
no_ocr: false
reprocess: false
```

Запуск:

```bash
python batch_extract.py --config extract.yaml
```

Удобно для повторяющихся запусков с одними параметрами.

---

## Production Features

### Валидация входа

```
ERROR: PDF directory not found: C:/NonExistent
ERROR: chunk_size must be > 0, got -1
ERROR: Output directory not writable: /root/protected
ERROR: Less than 1 GB free disk space (0.50 GB)
```

Все ошибки выводятся ПЕРЕД началом обработки.

### Атомарные операции

Если процесс упадёт:
- `.txt` файл пишется через временный файл → сразу переименовывается
- `.manifest.json` пишется так же
- Данные не теряются при краше или отключении диска

### OCR timeout

Если OCR зависает на картинке:

```
--ocr-timeout 60    # обычно 60 сек достаточно
--ocr-timeout 120   # для медленных CPU или GPU
```

Без timeout страница может зависнуть навсегда. С timeout — страница пропускается, обработка продолжается.

### Skip-on-repeated-failure

Если PDF #7 каждый раз вызывает краш:
- При первом краше → в `.extraction_blacklist.json`
- При втором запуске → автоматически пропускается

Можно вручную отредактировать `.extraction_blacklist.json` чтобы переобработать.

### Integrity validation

После каждого PDF скрипт проверяет:
- Совпадает ли длина `.txt` с `total_chars` в manifest (±10%)
- Есть ли страницы с `failed`
- Много ли `low_quality_pages`

```
  integrity check: Character count mismatch: txt=847293, manifest=845200
  integrity check: 2 page(s) failed to extract
```

### Resume + reprocess

```bash
# Первый запуск — обработает все
python batch_extract.py "C:/Books"

# Второй запуск — пропустит готовые, продолжит прерванные
python batch_extract.py "C:/Books"

# Переобработать всё заново
python batch_extract.py "C:/Books" --reprocess
```

---

## Выходные файлы

| Файл | Описание |
|---|---|
| `<stem>.txt` | Полный текст PDF |
| `<stem>.manifest.json` | Отчёт по каждой странице |
| `train.jsonl` | Все чанки всех PDF |
| `extraction_report.json` | Сводка: время, скорость, ошибки |
| `extraction.log` | Полный лог с временными метками |
| `.extraction_blacklist.json` | Список PDF-файлов с повторяющимися ошибками |

---

## Интерпретация вывода

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

| Метрика | Норма | Проблема |
|---|---|---|
| `errors=0` | Хорошо | Плохо если > 0 |
| `warnings` | 0–5 на PDF | много warnings → проверь лог |
| `low_q` | 0–2 на PDF | > 5% страниц → пересчитай с `--dpi 350` |
| `chars` | сотни тысяч | < 10K → скорее всего пустой или плохой PDF |

---

## Коды возврата

| Код | Значение |
|---|---|
| `0` | Успех, без ошибок |
| `1` | Завершено с ошибками |
| `130` | Прервано пользователем (Ctrl+C) |
