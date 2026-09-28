FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Single-threaded math/ML: the model is tiny; per-core OpenMP arenas are
    # what blew past Render Free's 512 MB limit on multi-core hosts.
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
# (torch comes from the CPU-only wheel index pinned in requirements.txt)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code + data FIRST so the build step can read the registry
COPY . .

# Offline embedding build: exports ONNX (fp32 + int8) from all-MiniLM-L6-v2,
# precomputes the registry embedding matrix, verifies ONNX/ST parity.
# Generated artifacts stay baked into the image; runtime never needs torch.
RUN python scripts/build_embeddings.py

# Safety net: the image ships precomputed artifacts; nothing to do at boot.
EXPOSE 8000

# Single worker is REQUIRED on Render Free: each worker duplicates the
# runtime + model memory. PORT is provided by Render at runtime.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
