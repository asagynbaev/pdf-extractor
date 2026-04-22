# Установка

## Требования

| Компонент | Минимум | Рекомендуется |
|---|---|---|
| Python | 3.10 | 3.12 |
| RAM | 4 GB | 8 GB |
| Диск | 2 GB (модели OCR) | 5 GB |
| ОС | Windows 10 x64 | Windows 11 x64 |
| GPU | — | NVIDIA (CUDA 11.8+) |

---

## Шаг 1 — Python

Проверь версию:

```bash
python --version
# Python 3.12.x
```

Если Python не установлен — скачай с [python.org](https://python.org). Ставь **Add to PATH** при установке.

---

## Шаг 2 — Виртуальное окружение

```bash
cd C:\Users\sagyn\Development\pdf-explainer

python -m venv .venv
.venv\Scripts\activate
```

После активации в начале строки появится `(.venv)`.

---

## Шаг 3 — PaddlePaddle

PaddlePaddle нужно ставить **до** остальных пакетов и **через отдельный индекс**:

### CPU (любая машина)

```bash
pip install "paddlepaddle==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
```

### GPU (NVIDIA CUDA 11.8)

```bash
pip install "paddlepaddle-gpu==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cu118/
```

### GPU (NVIDIA CUDA 12.3)

```bash
pip install "paddlepaddle-gpu==3.2.0" -i https://www.paddlepaddle.org.cn/packages/stable/cu123/
```

Проверь:

```bash
python -c "import paddle; paddle.utils.run_check()"
# PaddlePaddle is installed successfully!
```

---

## Шаг 4 — Остальные зависимости

```bash
pip install -r requirements.txt
```

---

## Шаг 5 — Первый запуск OCR (загрузка моделей)

При первом запуске PaddleOCR автоматически скачает модели (~300 MB):

```bash
python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='ru')"
```

Модели кешируются в `~/.paddleocr/` и при следующих запусках не скачиваются.

---

## Шаг 6 — `.env` файл (только для explain_pdf.py)

Скопируй пример и заполни:

```bash
copy .env.example .env
```

Открой `.env` и укажи:

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

`batch_extract.py` не требует `.env` и API-ключей.

---

## Проверка установки

```bash
python batch_extract.py --help
```

Должно вывести список всех параметров без ошибок.

---

## Возможные проблемы

### `ModuleNotFoundError: No module named 'paddle'`

PaddlePaddle не установлен или установлен в другое окружение. Убедись что `.venv` активирован и повтори шаг 3.

### OCR медленный

Без GPU PaddleOCR работает на CPU. Это нормально. Для 300-страничной книги: ~5-15 минут на CPU, ~1-2 минуты на GPU.

### `DLL load failed` (Windows)

Установи [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### Низкое качество OCR для русских книг

Используй `--lang ru` или `--lang cyrillic`. Для смешанных (ru + en) текстов — `--lang ru` достаточно.
