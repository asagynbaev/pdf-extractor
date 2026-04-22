# PDF Extractor — Production Dataset Pipeline

Батч-обработка сотен PDF-файлов → готовый датасет `train.jsonl` для файн-тюнинга LLM.  
**Production-ready**: нулевая потеря данных, атомарные операции, полное логирование, resume + blacklist.

## ⚡ 30 секунд

```bash
# Установка
pip install -r requirements.txt
pip install "paddlepaddle==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# Запуск
python batch_extract.py "C:/Books" --lang ru

# Результат
ls extracted/
  train.jsonl                  ← готово для файн-тюна
  extraction_report.json       ← статистика
```

## Возможности

✅ **Multi-column layouts** — корректная склейка столбцов  
✅ **Header/footer removal** — автоматическое удаление повторяющихся  
✅ **Hyperlinks preserved** — сохранение ссылок  
✅ **Footnotes** — переприсоединение сносок к тексту  
✅ **Cross-page merging** — соединение рваных абзацев  
✅ **Tables** → markdown  
✅ **Image OCR** — текст из встроенных картинок  
✅ **Full-page OCR** — поддержка отсканированных PDF  

### Production Features

✅ **Input validation** — все ошибки до обработки  
✅ **Atomic writes** — нет потери данных при краше  
✅ **OCR timeout** — не зависает на плохих картинках  
✅ **Integrity checks** — проверка целостности  
✅ **Resume + blacklist** — продолжение с пропуском повреждённых  
✅ **Quality Control** — health report + фильтрация низкокачественных чанков  
✅ **Config files** — YAML/JSON для повторов  
✅ **Full logging** — лог с временными метками  
✅ **Pinned versions** — воспроизводимость  

---

## Документация

| Документ | Для кого |
|---|---|
| [docs/installation.md](docs/installation.md) | Первый запуск, CPU/GPU, Windows |
| [docs/batch_extract.md](docs/batch_extract.md) | Параметры, конфиг, интерпретация вывода |
| [docs/output_formats.md](docs/output_formats.md) | Схема файлов, примеры JSON |
| [docs/architecture.md](docs/architecture.md) | Как работают алгоритмы |
| [extract.example.yaml](extract.example.yaml) | Пример конфиг-файла |

---

## Быстрый старт

### 1. Установка (Windows)

```bash
# Окружение
python -m venv .venv
.venv\Scripts\activate

# PaddlePaddle (CPU) — важно ставить первым!
pip install "paddlepaddle==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/

# Остальное
pip install -r requirements.txt
```

Если GPU (NVIDIA CUDA 11.8):
```bash
pip install "paddlepaddle-gpu==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
```

### 2. Один PDF

```bash
python batch_extract.py "C:/Books/HackingBook.pdf"
```

### 3. Папка PDF (типичный случай)

```bash
python batch_extract.py "C:/Books/Cybersec" --lang ru
```

### 4. Через конфиг (для повтора)

Скопируй пример и запусти:
```bash
cp extract.example.yaml extract.yaml
# отредактируй extract.yaml под себя
python batch_extract.py --config extract.yaml
```

---

## Результаты

```
extracted/
  ├─ Book1.txt                    (полный текст с метаданными)
  ├─ Book1.manifest.json          (отчёт по каждой странице)
  ├─ Book2.txt
  ├─ Book2.manifest.json
  ├─ ...
  ├─ train.jsonl                  (ГОТОВЫЙ датасет — высокое качество)
  ├─ train.lowquality.jsonl       (чанки для ручного просмотра)
  ├─ health_report.txt            (анализ качества OCR + рецепты ремонта)
  ├─ extraction_report.json       (сводка: время, скорость, ошибки)
  ├─ extraction.log               (полный лог)
  └─ .extraction_blacklist.json   (повреждённые файлы для пропуска)
```

**Основной датасет:**
- `train.jsonl` — прямое в файн-тюнинг (Unsloth, LLaMA-Factory, HuggingFace, и т.д.)
- `train.lowquality.jsonl` — проверь вручную, потом добавь или выброси

**Quality Control:**
- `health_report.txt` — список проблемных PDF + команды ремонта

---

## Параметры (по умолчанию ✓)

| Параметр | Умолч | Что означает |
|---|---|---|
| `--chunk` | 1024 | Размер чанка в словах (~2–3 страницы) |
| `--overlap` | 64 | Перекрытие между чанками |
| `--lang` | `ru` | PaddleOCR язык (ru / en / cyrillic / ch) |
| `--dpi` | 250 | OCR качество (250 норма, 350 для плохих сканов) |
| `--min-native` | 80 | Порог символов для пропуска OCR |
| `--conf` | 0.6 | Фильтрация низкокачественного OCR |
| `--ocr-timeout` | 60 | Таймаут OCR (сек, предотвращает зависания) |
| `--no-ocr` | — | Пропустить OCR (для текстовых PDF) |

Для типичной кибербез-книги 300 стр — дефолты идеальны. Для плохих сканов:
```bash
python batch_extract.py "C:/Books" --dpi 350 --conf 0.5
```

---

## Требования

- **Python** 3.10+
- **RAM** 4 GB минимум, 8 GB рекомендуется
- **Диск** 2 GB для моделей OCR + место под результаты
- **Зависимости** — пинированы в `requirements.txt` (воспроизводимость)

---

## FAQ

**Q: А если PDF повреждённый и вызывает краш?**  
A: Попадёт в `.extraction_blacklist.json` и будет пропущен при следующем запуске.

**Q: Сколько времени на 100 книг?**  
A: На CPU (~30 мин/книга без OCR, ~1–3 часа/книга с OCR). На GPU — в 10× быстрее.

**Q: Можно ли переобработать?**  
A: Да — `--reprocess` переделает всё. Или отредактируй `.extraction_blacklist.json`.

**Q: А если я запущу дважды?**  
A: Resume: пропустит готовые, продолжит с места остановки. Интегрити проверит уже готовые.

---

## Production Checklist

- [x] Input validation (все ошибки до обработки)
- [x] Atomic file writes (no data loss on crash)
- [x] OCR timeout (prevents hanging)
- [x] Integrity validation (check outputs)
- [x] Resume + blacklist (crash recovery)
- [x] Quality Control (health report + dataset filtering)
- [x] Config files (YAML/JSON)
- [x] Full logging (timestamps, ETA)
- [x] Pinned dependencies (reproducibility)
- [x] Error handling (nothing silently fails)
- [x] Documentation (5 docs + examples)
