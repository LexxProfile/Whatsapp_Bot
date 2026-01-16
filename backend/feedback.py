from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import mysql.connector
import os
import requests

router = APIRouter()

# --- 1. KONFIGURASI DATABASE ---
def get_db_connection():
    """Membuka koneksi ke database chatbot_history."""
    return mysql.connector.connect(
        host=os.getenv("DATABASE_HOST", "db"),
        port=int(os.getenv("DATABASE_PORT", 3306)),
        user=os.getenv("DATABASE_USER", "user_n8n"),
        password=os.getenv("DATABASE_PASSWORD", "root"),
        database="chatbot_history"
    )

# --- 2. KONFIGURASI AI (Hugging Face) ---
HF_TOKEN = os.getenv("HF_TOKEN")
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# URL Model untuk Sentiment, Intent, dan Summarization
SENTIMENT_URL = "https://api-inference.huggingface.co/models/w11wo/indonesian-roberta-base-sentiment-classifier"
INTENT_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-mnli"
SUMMARIZE_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

# --- 3. MODEL DATA ---
class FeedbackData(BaseModel):
    nama: str
    nomor_telepon: str
    bk_mobil: Optional[str] = None
    keluhan: Optional[str] = ""
    saran_masukan: str

# --- 4. LOGIKA ANALISIS DEEP LEARNING ---

def analyze_sentiment(text: str) -> str:
    """Analisis sentimen dengan proteksi kata negatif kuat."""
    text_lower = text.lower()
    # Daftar kata kunci yang pasti dianggap NEGATIVE oleh sistem (Override AI)
    strong_negative = ["bodoh", "goblok", "tolol", "anjing", "brengsek", "payah", "masalah", "hadeh", "kecewa", "jelek", "parah", "lambat"]
    
    if any(word in text_lower for word in strong_negative):
        return "NEGATIVE"

    # [TAMBAHAN] Cek Kata Positif Kuat (Agar 'Terima Kasih' masuk Positif)
    strong_positive = ["terima kasih", "terimakasih", "makasih", "thanks", "mantap", "bagus", "keren", "puas", "suka", "the best", "top", "oke", "ok", "good", "membantu"]
    
    if any(word in text_lower for word in strong_positive):
        return "POSITIVE"

    try:
        payload = {"inputs": text}
        response = requests.post(SENTIMENT_URL, headers=HEADERS, json=payload, timeout=5)
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                top_label = max(result[0], key=lambda x: x['score'])['label']
                return top_label.upper() # POSITIVE, NEUTRAL, NEGATIVE
    except:
        pass
    return "NEUTRAL"

def classify_intent(text: str) -> str:
    """Klasifikasi Niat: KELUHAN, PERTANYAAN, SARAN, atau PUJIAN."""
    candidate_labels = ["keluhan", "pertanyaan", "saran", "pujian"]
    payload = {
        "inputs": text,
        "parameters": {"candidate_labels": candidate_labels}
    }
    try:
        response = requests.post(INTENT_URL, headers=HEADERS, json=payload, timeout=7)
        if response.status_code == 200:
            return response.json()['labels'][0].upper()
    except:
        pass
    return "KELUHAN"

# --- 5. ENDPOINT POST FEEDBACK ---

@router.post("/api/feedback", tags=["Feedback"])
async def create_feedback(data: FeedbackData):
    conn = None
    cursor = None
    try:
        full_text = f"{data.keluhan} {data.saran_masukan}"
        
        # Proses AI
        sentiment = analyze_sentiment(full_text)
        intent = classify_intent(full_text)

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # INSERT dengan 9 kolom (Menambahkan created_at)
        query = """
            INSERT INTO feedback (nama, nomor_telepon, bk_mobil, keluhan, saran_masukan, sentiment_label, intent, sentiment_score, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        cursor.execute(query, (
            data.nama, data.nomor_telepon, data.bk_mobil, 
            data.keluhan, data.saran_masukan, sentiment, intent, 1.0
        ))
        conn.commit()

        # Respon dinamis untuk Frontend
        if sentiment == "NEGATIVE":
            pesan = f"Mohon maaf Kak {data.nama} atas ketidaknyamanannya. Masukan ini akan segera kami evaluasi agar layanan kami menjadi lebih baik."
        else:
            pesan = f"Terima kasih Kak {data.nama} atas masukannya! Kami sangat senang bisa melayani Anda hari ini."

        return {
            "status": "success",
            "message": pesan,
            "sentiment": sentiment,
            "intent": intent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- 6. ENDPOINT ADMIN: AMBIL SEMUA DATA (Sinkron dengan Dashboard) ---

@router.get("/api/admin/feedbacks", tags=["Admin"])
async def get_all_feedbacks():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Ambil data asli dari DB untuk ditampilkan di dashboard tanpa dummy
        cursor.execute("SELECT * FROM feedback ORDER BY created_at DESC")
        return cursor.fetchall()
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- 7. ENDPOINT ADMIN: AI SUMMARIZATION ---

@router.get("/api/admin/feedback/summary", tags=["Admin"])
async def get_ai_summary():
    """Meringkas data keluhan negatif asli untuk dashboard."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # [MODIFIKASI] Ambil semua feedback (Positif/Negatif) agar AI selalu punya data untuk diringkas
        cursor.execute("""
            SELECT keluhan, saran_masukan FROM feedback 
            ORDER BY created_at DESC LIMIT 15
        """)
        rows = cursor.fetchall()
        
        if not rows:
            return {"summary": "Belum ada data feedback yang cukup untuk dianalisis oleh AI."}

        # Gabungkan keluhan atau saran menjadi satu teks untuk AI
        text_parts = [r['keluhan'] or r['saran_masukan'] or "" for r in rows]
        combined_text = ". ".join([t for t in text_parts if t])
        
        if not combined_text.strip():
            return {"summary": "Data teks tidak cukup untuk diringkas."}

        # [PERBAIKAN] Tambahkan wait_for_model agar tidak error 503 saat model loading
        payload = {
            "inputs": combined_text,
            "options": {"wait_for_model": True}
        }

        res = requests.post(SUMMARIZE_URL, headers=HEADERS, json=payload, timeout=30)
        
        if res.status_code == 200:
            result = res.json()
            summary = result[0]['summary_text'] if isinstance(result, list) else result.get('summary_text', 'Gagal meringkas.')
            return {"summary": summary}
        else:
            print(f"AI Error ({res.status_code}): {res.text}") # Log error ke terminal untuk debugging
            return {"summary": "Sistem sedang sibuk memproses data. Silakan refresh kembali sesaat lagi."}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if cursor: cursor.close()
        if conn: conn.close()