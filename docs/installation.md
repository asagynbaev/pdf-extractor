# Installation

## Requirements

| Component | Minimum | Recommended |
|---|---|---|
| Python | 3.10 | 3.12 |
| RAM | 4 GB | 8 GB |
| Disk | 2 GB (OCR models) | 5 GB |
| OS | Windows 10 x64 | Windows 11 x64 |
| GPU | — | NVIDIA (CUDA 11.8+) |

---

## Step 1 — Python

Check your version:

```bash
python --version
# Python 3.12.x
```

If Python is not installed, download it from [python.org](https://python.org). Make sure to check **Add to PATH** during installation.

---

## Step 2 — Virtual Environment

```bash
cd C:\Users\sagyn\Development\pdf-explainer

python -m venv .venv
.venv\Scripts\activate
```

After activation, you should see `(.venv)` at the start of your terminal line.

---

## Step 3 — PaddlePaddle

PaddlePaddle must be installed **before** other packages and **from a custom index**:

### CPU (Any Machine)

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

Verify installation:

```bash
python -c "import paddle; paddle.utils.run_check()"
# PaddlePaddle is installed successfully!
```

---

## Step 4 — Other Dependencies

```bash
pip install -r requirements.txt
```

---

## Step 5 — First OCR Run (Model Download)

On first run, PaddleOCR will automatically download models (~300 MB):

```bash
python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='en')"
```

Models are cached in `~/.paddleocr/` and will not be re-downloaded on subsequent runs.

---

## Step 6 — Verification

```bash
python batch_extract.py --help
```

Should display all parameters without errors.

---

## Common Issues

### `ModuleNotFoundError: No module named 'paddle'`

PaddlePaddle is not installed or installed in a different environment. Make sure `.venv` is activated and repeat Step 3.

### OCR is Slow

Without GPU, PaddleOCR runs on CPU. This is normal. For a 300-page book: ~5-15 minutes on CPU, ~1-2 minutes on GPU.

### `DLL load failed` (Windows)

Install [Microsoft Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe).

### Low OCR Quality for Non-English Documents

Use `--lang ru` (Russian), `--lang zh` (Chinese), or `--lang cyrillic` for Cyrillic scripts. For mixed language documents (e.g., Russian + English), `--lang ru` is sufficient.
