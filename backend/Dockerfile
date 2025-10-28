# Gunakan base image Python
FROM python:3.9-slim

# Set direktori kerja di dalam kontainer
WORKDIR /app

# Salin file requirements dan install library
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Salin semua kode aplikasi
COPY . .

# Perintah untuk menjalankan aplikasi saat kontainer dimulai
# Uvicorn akan menjalankan FastAPI app di dalam file main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]