# Gunakan base image Python
FROM python:3.11-slim

# Set direktori kerja di dalam kontainer
WORKDIR /app

# Salin file requirements
COPY requirements.txt requirements.txt

# ==============================================================================
# --- INSTALASI DEPENDENSI SISTEM (WEASYPRINT & BUILD ESSENTIALS) ---
# FIX: Menginstal libpango, libgobject, MySQL headers, dan Python dev headers
# ==============================================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Dependensi WeasyPrint (Graphics & Text Rendering)
    libpango-1.0-0 \
    libharfbuzz-icu0 \
    libharfbuzz-dev \
    libgobject-2.0-0 \
    libglib2.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libffi-dev \
    fonts-dejavu \
    build-essential \
    default-libmysqlclient-dev \
    python3-dev \
    \
    # Cleanup untuk mengurangi ukuran image
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    # Pastikan perintah 'python' merujuk ke 'python3'
    && ln -s /usr/local/bin/python /usr/bin/python
# ----------------------------------------------------------------------

# Install library Python (Ini akan berhasil karena tools sudah terinstal)
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua kode aplikasi
COPY . .

# Perintah untuk menjalankan aplikasi saat kontainer dimulai
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]