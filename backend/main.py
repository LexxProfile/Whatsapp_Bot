import os
from dotenv import load_dotenv
import bcrypt
import uuid
import jwt
from typing import Optional, Union, List, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, Depends, status, Form, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from weasyprint import HTML, CSS
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse # [TAMBAHKAN] Impor HTMLResponse
from pydantic import BaseModel
import mysql.connector
from pathlib import Path
import math
import time
import requests
import json
from fastapi import Request
from analisisdata import router as analisisdata_router
from feedback import router as feedback_router

load_dotenv()

SENDABLE_API_KEY = os.getenv("SENDABLE_API_KEY")
WHATSAPP_API_URL = "https://api.sendable.dev/w/messages.send"
PUBLIC_BASE_URL = "https://endlessproject.my.id/api/invoices"
FRONTEND_BUILD_DIR = Path("./frontend-build")
LOCAL_SAVE_DIR = FRONTEND_BUILD_DIR / "invoices"

# --- Konfigurasi ---
app = FastAPI(title="Chatbot Backend API", description="API untuk mengelola user dan riwayat chat.")

LOCAL_SAVE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/invoices", StaticFiles(directory=LOCAL_SAVE_DIR), name="invoices")

# [ADD] Endpoint fallback/eksplisit untuk memastikan file bisa diakses via /api
@app.get("/api/invoices/{filename}")
async def get_invoice_api(filename: str):
    file_path = LOCAL_SAVE_DIR / filename
    if file_path.exists():
        return FileResponse(file_path)
    raise HTTPException(status_code=404, detail="Invoice not found")

# --- Konfigurasi CORS ---
origins = [
    "http://119.28.110.17:3000",
    "http://endlessproject.my.id",   # Tambahkan ini
    "https://endlessproject.my.id"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CAR_COLUMN_MAPPING = {
    "Chery Omoda 5": [
        "Omoda 5 RZ", "OMODA 5 Z", "OMODA 5GT FWD", 
        "OMODA 5GT AWD", "OMODA 5 EV", "C5 RZ", "C5 Z"
    ],
    "Chery Tiggo 7 Pro": [
        "TIGGO 7 PREMIUM", "TIGGO 7 LUXURY", "TIGGO 7 COMFORT"
    ],
    "Chery Tiggo 8 Pro": [
        "TIGGO 8 CSH", "TIGGO 8 PRO PREMIUM", "TIGGO 8 PRO LUXURY", 
        "TIGGON PRO 8 1.6 COMFORT", "TIGGO 8 PRO 1.6 PREMIUM", "TIGGO 8 PRO MAX"
    ],
    "Chery Tiggo 5X": [
        "TIGGO CROSS" # Asumsi Tiggo 5X menggunakan kolom Tiggo Cross atau J6 (sesuaikan jika ada kolom lain)
    ],
    "Jaecoo J6": [
        "J6 IWD", "J6 RWD"
    ]
}

# Ambil konfigurasi dari environment variables Docker Compose
DATABASE_HOST = os.getenv("DATABASE_HOST", "db")
DATABASE_PORT = int(os.getenv("DATABASE_PORT", 3306))
DATABASE_USER = os.getenv("DATABASE_USER", "user_n8n")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD") 
DATABASE_NAME = os.getenv("DATABASE_NAME", "chatbot_history")
# Pastikan JWT_SECRET kuat dan diambil dari environment variable di production!
JWT_SECRET = os.getenv("JWT_SECRET")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Token berlaku 1 jam

class ItemInvoice(BaseModel):
    code: str
    name: str
    price: float
    type: str
    quantity: float
    lc_per_hour: float

# [Model 2] Detail Pelanggan
class CustomerDetails(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    plate: Optional[str] = None
    note: Optional[str] = None

# [Model 3] Payload Utama (Memanggil Model 1 & 2)
class InvoicePayload(BaseModel):
    customer: CustomerDetails
    car: dict
    items: List[ItemInvoice]
    totals: Dict[str, Any]

# --- Model Data Pydantic ---
class UserCreate(BaseModel):
    phone_number: str
    password: str

class UserLogin(BaseModel):
    phone_number: str # Frontend akan mengirim ini sebagai phone_number
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    status: Optional[str] = None

class TokenData(BaseModel):
    phone_number: Optional[str] = None

class OrderCreate(BaseModel):
    item_name: str
    quantity: int
    chat_id: Optional[int] = None # Tambahkan chat_id
    # Harga dan total bisa ditambahkan di sini jika perlu
    # item_price: float

# Model untuk update status
class OrderStatusUpdate(BaseModel):
    status: str

# --- Koneksi Database ---
def get_db_connection():
    retries = 5
    while retries > 0:
        try:
            print(f"Mencoba menghubungkan ke database di {DATABASE_HOST}:{DATABASE_PORT}...")
            conn = mysql.connector.connect(
                host=DATABASE_HOST,
                port=DATABASE_PORT,
                user=DATABASE_USER,
                password=DATABASE_PASSWORD,
                database=DATABASE_NAME,
                connection_timeout=10
            )
            if conn.is_connected():
                print("Koneksi database berhasil.")
                return conn
        except mysql.connector.Error as err:
            print(f"Gagal koneksi ke {DATABASE_HOST}:{DATABASE_PORT} ({retries} percobaan tersisa): {err}")
            retries -= 1
            
            if retries == 0:
                print("Gagal total menghubungkan ke database setelah beberapa kali percobaan.")
                if err.errno == mysql.connector.errorcode.ER_ACCESS_DENIED_ERROR:
                    raise HTTPException(status_code=401, detail=f"Akses database ditolak untuk user '{DATABASE_USER}'")
                elif err.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                    raise HTTPException(status_code=404, detail=f"Database '{DATABASE_NAME}' tidak ditemukan")
                else:
                    raise HTTPException(status_code=500, detail=f"Tidak dapat terhubung ke database: {err}")
            time.sleep(5) # Menunggu sedikit lebih lama sebelum mencoba lagi
        except Exception as e:
            print(f"Error tidak terduga saat koneksi DB: {e}")
            raise HTTPException(status_code=500, detail="Error server internal.")



# --- Fungsi Utilitas Keamanan ---
def hash_password(password: str) -> str:
    """Meng-hash password menggunakan bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Memverifikasi password plain dengan hash."""
    if not plain_password or not hashed_password:
        print("DEBUG: Plain password atau hashed password kosong/None.")
        return False # Tidak bisa verifikasi jika salah satu kosong atau None
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError as e:
        print(f"DEBUG: Error verifying password (Invalid salt or malformed hash): {e}")
        return False # Perlakukan hash yang rusak sebagai password yang salah
    
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Membuat token JWT."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiry time
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)
    return encoded_jwt

# Skema OAuth2 untuk dependensi (meskipun login tidak pakai form)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Mendekode token JWT dan mengembalikan nomor telepon (subject)."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        phone_number: Optional[str] = payload.get("sub")
        if phone_number is None:
            raise credentials_exception
        # Di sini Anda bisa menambahkan pengecekan user ke DB jika perlu
        return phone_number
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except jwt.PyJWTError as e:
         print(f"JWT Error: {e}") # Log error JWT
         raise credentials_exception
    except Exception as e:
        print(f"Unexpected error in get_current_user: {e}") # Log error tak terduga
        raise credentials_exception

# --- Endpoints API ---

@app.get("/", response_class=FileResponse)
async def read_root():
    index_path = FRONTEND_BUILD_DIR / "chery.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail=f"File frontend 'chery.html' tidak ditemukan di path: {index_path.resolve()}")
    return FileResponse(index_path)

class RegisterRequest(BaseModel):
    phone_number: str
    password: str
    captcha_token: str

@app.post("/api/register-request")
async def register_request(data: RegisterRequest, request: Request):
    print(f"Menerima permintaan registrasi untuk: {data.phone_number}") # LOG 1

    # 1. VALIDASI CAPTCHA (WAJIB)
    captcha_verify = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={
            "secret": os.getenv("TURNSTILE_SECRET"),
            "response": data.captcha_token
        }
    ).json()
    
    print(f"Hasil verifikasi CAPTCHA: {captcha_verify}") # LOG 2

    if not captcha_verify.get("success"):
        print("Verifikasi CAPTCHA gagal.") # LOG 3
        raise HTTPException(status_code=400, detail="CAPTCHA tidak valid")

    # 2. VALIDASI FORMAT NOMOR
    if not data.phone_number.startswith("62"):
        print(f"Format nomor telepon salah: {data.phone_number}") # LOG 4
        raise HTTPException(status_code=400, detail="Format nomor tidak valid")

    # 3. CEK NOMOR SUDAH TERDAFTAR (READ ONLY)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT phone_number FROM users WHERE phone_number = %s",
        (data.phone_number,)
    )
    if cursor.fetchone():
        print(f"Nomor {data.phone_number} sudah terdaftar.") # LOG 5
        cursor.close()
        conn.close()
        raise HTTPException(status_code=400, detail="Nomor sudah terdaftar")

    # 4. SIMPAN KE DATABASE
    try:
        hashed_pw = hash_password(data.password)
        cursor.execute(
            "INSERT INTO users (phone_number, password_hash, role, status, created_at) VALUES (%s, %s, %s, %s, NOW())",
            (data.phone_number, hashed_pw, 'staff', 'pending')
        )
        conn.commit()
    except Exception as e:
        print(f"Error saving user: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan data user")
    finally:
        cursor.close()
        conn.close()

    # 5. RESPONSE KE FRONTEND
    return {
        "status": "success",
        "message": "Registrasi berhasil. "
    }


class UserLogin(BaseModel):
    phone_number: str
    password: str
    captcha_token: str


@app.post("/api/login", response_model=Token)
async def login_for_access_token(user: UserLogin):
    conn = None
    cursor = None
    try:
        # 1️⃣ VALIDASI CAPTCHA
        try:
            captcha_verify = requests.post(
                "https://challenges.cloudflare.com/turnstile/v0/siteverify",
                data={
                    "secret": os.getenv("TURNSTILE_SECRET"),
                    "response": user.captcha_token
                },
                timeout=5 # Add a timeout for external request
            ).json()
        except requests.exceptions.RequestException as e:
            print(f"CAPTCHA verification failed due to network/API error: {e}")
            raise HTTPException(status_code=503, detail="CAPTCHA service unavailable. Please try again.")

        if not captcha_verify.get("success"):
            raise HTTPException(status_code=400, detail="CAPTCHA tidak valid")

        # 2️⃣ CEK USER DI DATABASE
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT phone_number, password_hash, status FROM users WHERE phone_number = %s",
            (user.phone_number,)
        )
        user_db = cursor.fetchone()

        if not user_db:
            raise HTTPException(
                status_code=401,
                detail="Nomor telepon atau password salah"
            )

        # 3️⃣ VERIFIKASI PASSWORD
        if not verify_password(user.password, user_db["password_hash"]):
            raise HTTPException(
                status_code=401,
                detail="Nomor telepon atau password salah"
            )

        # 4️⃣ BUAT TOKEN
        access_token = create_access_token(
            data={"sub": user_db["phone_number"]}
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "status": user_db["status"]
        }
    except HTTPException:
        raise # Re-raise HTTPException to be handled by FastAPI
    except Exception as e:
        print(f"Login unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Terjadi kesalahan server internal.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if not user_db:
        raise HTTPException(
            status_code=401,
            detail="Nomor telepon atau password salah"
        )

    # 3️⃣ VERIFIKASI PASSWORD
    if not verify_password(user.password, user_db["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Nomor telepon atau password salah"
        )

    # 4️⃣ BUAT TOKEN
    access_token = create_access_token(
        data={"sub": user_db["phone_number"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "status": user_db["status"]
    }


# --- Sertakan Router Analisis Data (Feedback) ---
# Kita hapus dependencies global di sini agar POST /api/feedback bisa diakses publik
app.include_router(analisisdata_router)

# --- Sertakan Router Feedback (Dari feedback.py) ---
app.include_router(feedback_router)

# --- New Endpoint for User Profile ---
# --- [REVISI] Endpoint User Profile dengan Fallback Aman ---
@app.get("/api/user/profile")
async def get_user_profile(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Eksekusi query untuk mengambil role
        # [FIXED] Membuat query lebih fleksibel untuk menangani format nomor telepon yang berbeda
        # (misal: 0812... vs 62812...)
        phone_with_62 = current_user_phone
        if current_user_phone.startswith('0'):
            phone_with_62 = '62' + current_user_phone[1:]
        
        phone_with_0 = current_user_phone
        if current_user_phone.startswith('62'):
            phone_with_0 = '0' + current_user_phone[2:]
            
        # Query sekarang mencari semua variasi format nomor telepon
        cursor.execute("SELECT role FROM users WHERE phone_number IN (%s, %s, %s)", (current_user_phone, phone_with_62, phone_with_0))
        user_row = cursor.fetchone()
        
        # CASE 1: Data User tidak ada di Database
        if not user_row:
            print(f"CRITICAL: User dengan nomor {current_user_phone} tidak ditemukan di tabel users!")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"User {current_user_phone} tidak terdaftar di database."
            )
        
        # CASE 2: Kolom role ada tapi nilainya NULL
        if user_row.get("role") is None:
            print(f"CRITICAL: Kolom role untuk {current_user_phone} bernilai NULL!")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Role user belum diatur (NULL). Silakan isi di database."
            )
        
        # Jika semua oke, baru return (Hanya untuk perbandingan)
        return {"role": user_row["role"]}

    except mysql.connector.Error as db_err:
        # CASE 3: Error Database (misal kolom 'role' tidak ada)
        print(f"DATABASE ERROR DETECTED: {db_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Masalah Database: {str(db_err)}"
        )
    except Exception as e:
        # CASE 4: Error lainnya
        print(f"UNEXPECTED ERROR: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error sistem: {str(e)}"
        )
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# Model Pydantic untuk update user
class UserUpdate(BaseModel):
    role: str
    status: str

# 1. Endpoint Ambil Semua User
@app.get("/api/admin/users")
async def get_all_users(current_user: str = Depends(get_current_user)):
    # Validasi role harus Owner/Manager
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id, phone_number, role, status, created_at FROM users")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

# 2. Endpoint Update Role/Status
@app.put("/api/admin/users/{user_id}")
async def update_user(user_id: int, data: UserUpdate, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET role = %s, status = %s WHERE id = %s",
            (data.role, data.status, user_id)
        )
        conn.commit()
        return {"message": "User updated successfully"}
    finally:
        cursor.close()
        conn.close()

# 3. Endpoint Hapus User
@app.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: int, current_user: str = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
        return {"message": "User deleted"}
    finally:
        cursor.close()
        conn.close()
        
        
        
# --- Endpoint History (Memerlukan Otentikasi) ---
@app.get("/api/chat-history")
async def read_chat_history(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # [FIXED] Membuat query lebih fleksibel untuk menangani format nomor telepon yang berbeda
        # (misal: 0812... vs 62812...)
        phone_with_62 = current_user_phone
        if current_user_phone.startswith('0'):
            phone_with_62 = '62' + current_user_phone[1:]
        
        phone_with_0 = current_user_phone
        if current_user_phone.startswith('62'):
            phone_with_0 = '0' + current_user_phone[2:]
            
        # Query sekarang mencari semua variasi format nomor telepon
        cursor.execute(
            "SELECT id, waktu, chat_recipient, response_agent FROM chat_history WHERE recipient_id IN (%s, %s, %s, CONCAT(%s, '@s.whatsapp.net'), CONCAT(%s, '@s.whatsapp.net')) ORDER BY waktu DESC LIMIT 50",
            (current_user_phone, phone_with_62, phone_with_0, phone_with_62, phone_with_0)
        )
        history_from_db = cursor.fetchall()

        # "Menerjemahkan" nama kolom dari database ke format yang diharapkan frontend
        formatted_history = []
        for row in history_from_db:
            formatted_row = {
                "id": row.get("id"),
                "user_message": row.get("chat_recipient"), # chat_recipient -> user_message
                "bot_response": row.get("response_agent"), # response_agent -> bot_response
                "waktu": row.get("waktu").isoformat() if row.get("waktu") and isinstance(row.get("waktu"), datetime) else None
            }
            formatted_history.append(formatted_row)


        return formatted_history

    except mysql.connector.Error as err:
        print(f"History DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengambil riwayat chat.")
    except HTTPException as http_err:
        raise http_err # Lemparkan error otentikasi
    except Exception as e:
        print(f"History Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Endpoint untuk MEMBUAT Orderan Baru (Memerlukan Otentikasi) --- [FIXED]
@app.post("/api/orders", status_code=status.HTTP_201_CREATED)
async def create_order(order_data: OrderCreate, current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Menggabungkan item dan kuantitas menjadi satu string untuk kolom 'items'
        items_description = f"{order_data.item_name} (Qty: {order_data.quantity})"

        # Query untuk memasukkan data ke tabel 'orders'
        # ASUMSI: Nama pelanggan dan alamat bisa diisi nanti atau diambil dari profil user
        cursor.execute(
            """
            INSERT INTO orders (user_phone_number, customer_name, address, items, status, waktu)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                current_user_phone,
                "From Chat History", # Placeholder untuk nama pelanggan
                "Alamat belum diisi", # Placeholder untuk alamat
                items_description,
                "Baru", # Status default
                datetime.now(timezone(timedelta(hours=7))) # Waktu saat ini (WIB)
            )
        )
        conn.commit()
        return {"message": "Order berhasil ditambahkan"}

    except mysql.connector.Error as err:
        print(f"Create Order DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan pada database saat membuat orderan.")
    except HTTPException as http_err:
        # Melemparkan kembali error otentikasi dari get_current_user
        raise http_err
    except Exception as e:
        print(f"Create Order Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga saat membuat orderan.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Endpoint untuk MEMBACA Daftar Orderan (Memerlukan Otentikasi) --- [FIXED AGAIN]
@app.get("/api/orders/list") # Pastikan URL ini unik
async def read_orders(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # [FIXED] Membuat query lebih fleksibel untuk menangani format nomor telepon yang berbeda
        # (misal: 0812... vs 62812...)
        # 1. Buat versi '62' dari nomor telepon jika dimulai dengan '0'
        phone_with_62 = current_user_phone
        if current_user_phone.startswith('0'):
            phone_with_62 = '62' + current_user_phone[1:]
        
        # 2. Buat versi '0' dari nomor telepon jika dimulai dengan '62'
        phone_with_0 = current_user_phone
        if current_user_phone.startswith('62'):
            phone_with_0 = '0' + current_user_phone[2:]
        
        cursor.execute(
            # HANYA TAMPILKAN ORDERAN YANG STATUSNYA 'Baru'
            "SELECT id, waktu, customer_name, address, items, status FROM orders WHERE user_phone_number IN (%s, %s, %s) AND status = 'Baru' ORDER BY waktu DESC LIMIT 50",
            (current_user_phone, phone_with_62, phone_with_0)
        )
        orders_from_db = cursor.fetchall()

        # Format waktu ke ISO string agar konsisten
        for order in orders_from_db:
            if order.get('waktu') and isinstance(order.get('waktu'), datetime):
                order['waktu'] = order['waktu'].isoformat()

        return orders_from_db

    except mysql.connector.Error as err:
        print(f"Orders DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengambil daftar orderan.")
    except Exception as e:
        print(f"Orders Unexpected Error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Terjadi kesalahan tidak terduga saat mengambil orderan.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# ... (impor lain, app, CORS, koneksi DB, dll.) ...

# --- Fungsi Bantuan untuk Membersihkan Harga ---
def clean_price_string(price_str: Optional[str]) -> Optional[Union[int, float]]:
    """Membersihkan string harga (Rp, ., ,) dan mengonversinya ke angka."""
    if price_str is None or not isinstance(price_str, str):
        return None # Mengembalikan None jika input tidak valid, sesuai dengan type hint

    try:
        # Hapus 'Rp ', '.', dan ganti ',' (jika ada sebagai pemisah desimal) dengan '.'
        cleaned_str = price_str.replace('Rp ', '').replace('.', '').replace(',', '.')
        # Konversi ke float jika ada desimal, jika tidak, coba int
        if '.' in cleaned_str:
             # Coba float, jika gagal (misal: "N/A"), kembalikan 0
             try:
                 return float(cleaned_str)
             except ValueError:
                 return None # Mengembalikan None jika parsing float gagal
        else:
             # Coba integer, jika gagal, kembalikan 0
             try:
                 return int(cleaned_str)
             except ValueError:
                 return None # Mengembalikan None jika parsing int gagal
    except Exception:
        # Tangkap error lain jika terjadi saat pembersihan
        return None # Mengembalikan None jika ada masalah tak terduga



# --- Endpoint untuk MENGAMBIL Data Sparepart (Sudah Dimodifikasi) ---
@app.get("/api/spareparts")
async def get_spareparts(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) # Menggunakan dictionary cursor

        # Ambil kolom yang relevan dari database
        # Pastikan nama kolom di query ini sama persis dengan di DB Anda
        cursor.execute("""
            SELECT
                `nomor_sparepart` as part_number,
                `nama_sparepart` as part_name,
                `harga_jual_exc_tax` as price_str  -- Ambil sebagai string
            FROM sparepart_data
        """)
        spareparts_from_db = cursor.fetchall()

        # --- LANGKAH PEMBERSIHAN DAN KONVERSI ---
        cleaned_spareparts = []
        for part in spareparts_from_db:
            cleaned_price = clean_price_string(part.get("price_str")) # Panggil fungsi pembersih
            cleaned_spareparts.append({ # Frontend mengharapkan price berupa angka, atau null jika tidak ditemukan/invalid
                "part_number": part.get("part_number", "").strip(), # Tambah .strip() juga
                "part_name": part.get("part_name", "").strip(),
                "price": cleaned_price # Masukkan harga yang sudah jadi angka
            })
        # ----------------------------------------

        return cleaned_spareparts # Kirim data yang sudah bersih ke frontend

    except mysql.connector.Error as err:
        print(f"Spareparts DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Gagal mengambil data sparepart.")
    # ... (sisa error handling sama) ...
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()



# --- [BARU] Endpoint untuk MEMULAI Sesi Pembayaran ---
@app.post("/api/payments/initiate", status_code=status.HTTP_201_CREATED)
async def initiate_payment(
    order_ids: str = Form(...), # "1,2,3"
    total_amount: float = Form(...),
    item_details: str = Form(...), # Menerima detail item sebagai string JSON
    current_user_phone: str = Depends(get_current_user) # Otentikasi
):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Buat ID transaksi yang unik
        transaction_id = str(uuid.uuid4())

        # [FIX] Hitung waktu kedaluwarsa menggunakan zona waktu WIB (UTC+7) agar konsisten dengan DB
        wib_timezone = timezone(timedelta(hours=7))
        expires_at = datetime.now(wib_timezone) + timedelta(minutes=5)

        # 2. Simpan detail transaksi ke tabel baru `payment_transactions`
        cursor.execute(
            """
            INSERT INTO payment_transactions (id, order_ids, total_amount, item_details, expires_at, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (transaction_id, order_ids, total_amount, item_details, expires_at, 'PENDING')
        )
        conn.commit()

        # [FIX] Langsung ubah status orderan menjadi 'Menunggu Pembayaran'
        # agar tidak muncul lagi di halaman orderan.
        if order_ids:
            ids_to_update = tuple(map(int, order_ids.split(',')))
            if ids_to_update:
                query = "UPDATE orders SET status = 'Menunggu Pembayaran' WHERE id IN ({})".format(','.join(['%s'] * len(ids_to_update)))
                update_cursor = conn.cursor()
                update_cursor.execute(query, ids_to_update)
                update_cursor.close()
                conn.commit()

        # 3. Kembalikan ID transaksi ke frontend
        return {"transaction_id": transaction_id}

    except mysql.connector.Error as err:
        print(f"Initiate Payment DB Error: {err}")
        raise HTTPException(status_code=500, detail="Gagal memulai sesi pembayaran.")
    except Exception as e:
        print(f"Initiate Payment Unexpected Error: {e}")
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan tidak terduga: {e}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- [BARU] Endpoint untuk MEMERIKSA Status Pembayaran ---
@app.get("/api/payments/status/{transaction_id}")
async def get_payment_status(transaction_id: str):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT status, expires_at FROM payment_transactions WHERE id = %s", (transaction_id,))
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan.")

        # [FIX] Cek kedaluwarsa menggunakan zona waktu WIB (UTC+7)
        wib_timezone = timezone(timedelta(hours=7))
        # Tambahkan .replace(tzinfo=wib_timezone) untuk membuat waktu dari DB menjadi 'aware'
        db_expires_at = transaction['expires_at'].replace(tzinfo=wib_timezone) if transaction.get('expires_at') else None

        if transaction['status'] == 'PENDING' and db_expires_at and datetime.now(wib_timezone) > db_expires_at:
            # Update status di DB menjadi EXPIRED agar tidak dicek lagi
            cursor.execute("UPDATE payment_transactions SET status = 'GAGAL' WHERE id = %s", (transaction_id,))
            conn.commit()
            return {"status": "GAGAL"}

        return {"status": transaction['status']}

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database error: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- [BARU] Endpoint untuk MEMBACA Riwayat Pembayaran ---
@app.get("/api/payments/history")
async def get_payment_history(current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        # Menggunakan cursor dictionary untuk mendapatkan hasil sebagai objek
        cursor = conn.cursor(dictionary=True)

        # [FIX] Handle phone number variations (08 vs 62)
        phone_with_62 = current_user_phone
        if current_user_phone.startswith('0'):
            phone_with_62 = '62' + current_user_phone[1:]
        
        phone_with_0 = current_user_phone
        if current_user_phone.startswith('62'):
            phone_with_0 = '0' + current_user_phone[2:]

        # Query untuk mengambil semua transaksi berdasarkan order yang dimiliki user
        # Ini adalah query yang cukup kompleks, menggabungkan data dari 'orders' dan 'payment_transactions'
        query = """
            SELECT DISTINCT pt.*
            FROM payment_transactions pt
            JOIN orders o ON FIND_IN_SET(o.id, pt.order_ids)
            WHERE o.user_phone_number IN (%s, %s, %s)
            ORDER BY pt.created_at DESC;
        """
        cursor.execute(query, (current_user_phone, phone_with_62, phone_with_0))
        history = cursor.fetchall()

        wib_timezone = timezone(timedelta(hours=7))
        now_wib = datetime.now(wib_timezone)

        # Format waktu ke ISO string agar konsisten di frontend
        for record in history:
            # [FIX] Cek dan update status kedaluwarsa secara proaktif
            if record.get('status') == 'PENDING' and record.get('expires_at'):
                # Waktu dari DB adalah naive, jadi kita buat aware
                db_expires_at = record['expires_at'].replace(tzinfo=wib_timezone)
                print(f"DEBUG HISTORY: Transaction ID: {record['id']}")
                print(f"DEBUG HISTORY: now_wib: {now_wib}")
                print(f"DEBUG HISTORY: db_expires_at: {db_expires_at}")
                print(f"DEBUG HISTORY: now_wib > db_expires_at: {now_wib > db_expires_at}")
                if now_wib > db_expires_at:
                    # Update status di DB
                    update_cursor = conn.cursor()
                    update_cursor.execute("UPDATE payment_transactions SET status = 'GAGAL' WHERE id = %s", (record['id'],))
                    conn.commit()
                    update_cursor.close()
                    # Update status di data yang akan dikirim ke frontend
                    record['status'] = 'GAGAL'

            if record.get('created_at'):
                record['created_at'] = record['created_at'].isoformat()

            if record.get('expires_at'):
                record['expires_at'] = record['expires_at'].isoformat()

        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil riwayat pembayaran: {e}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- [MODIFIKASI] Endpoint untuk MENGONFIRMASI Pembayaran ---
@app.post("/api/payments/confirm/{transaction_id}")
async def confirm_payment(transaction_id: str):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Ambil detail transaksi
        cursor.execute("SELECT order_ids, status, expires_at FROM payment_transactions WHERE id = %s", (transaction_id,))
        transaction = cursor.fetchone()

        if not transaction:
            raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan.")
        if transaction['status'] == 'LUNAS':
            return {"message": "Pembayaran ini sudah pernah dikonfirmasi."}
        
        # [FIX] Cek kedaluwarsa menggunakan zona waktu WIB (UTC+7)
        wib_timezone = timezone(timedelta(hours=7))
        # Tambahkan .replace(tzinfo=wib_timezone) untuk membuat waktu dari DB menjadi 'aware'
        db_expires_at = transaction['expires_at'].replace(tzinfo=wib_timezone) if transaction.get('expires_at') else None

        if db_expires_at and datetime.now(wib_timezone) > db_expires_at:
            raise HTTPException(status_code=400, detail="Waktu pembayaran telah habis. Silakan buat transaksi baru.")

        # 2. Update status di tabel `payment_transactions` menjadi 'LUNAS'
        cursor.execute("UPDATE payment_transactions SET status = 'LUNAS' WHERE id = %s", (transaction_id,))

        # 3. Update status di tabel `orders`
        # Logika ini sudah dipindahkan ke `initiate_payment`.
        # Di sini kita hanya perlu commit perubahan status transaksi pembayaran.
                
        conn.commit()

        return {"message": "Pembayaran berhasil dikonfirmasi."}

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Gagal konfirmasi pembayaran: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- Endpoint Services (Pastikan Tabel services_data ADA) ---
@app.get("/api/services") 
async def get_services(car_model: Optional[str] = Query(None, description="Tipe mobil yang dipilih untuk filtering"),
    current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        
        sql = """
          SELECT 
            code, jenis_pekerjaan AS name, labor_charge AS price, 
            tipe_kendaraan, lc_per_hour, flat_rate
          FROM services_data
        """
        params = []
        
        # --- LOGIKA FILTERING ---
        if car_model:
            normalized_model = car_model.upper().strip()
            
            # Membuat list pencarian, yang mencakup model spesifik dan root model.
            search_models = ['ALL MODEL', normalized_model]
            
            # Logika Fuzzy / Generic Root
            if 'OMODA 5' in normalized_model:
                search_models.append('OMODA 5')
            elif 'TIGGO 7' in normalized_model:
                search_models.append('TIGGO 7')
            elif 'TIGGO 8' in normalized_model:
                search_models.append('TIGGO 8')
            elif 'J6' in normalized_model:
                search_models.append('J6')

            # Hapus duplikasi
            unique_models = list(set(search_models))
            
            # Membangun Klausa WHERE menggunakan 'IN'
            placeholders = ', '.join(['%s'] * len(unique_models))
            sql += f" WHERE tipe_kendaraan IN ({placeholders})"
            params = unique_models

        cursor = conn.cursor(dictionary=True)
        print(f"Executing SQL: {sql} with params: {params}") # DEBUGGING
        
        cursor.execute(sql, tuple(params)) 
        services_from_db = cursor.fetchall()
        
        formatted_services = []
        for service in services_from_db:
            formatted_services.append({
                "code": service.get("code", "").strip(),
                "name": service.get("name", "").strip(),
                "price": service.get("price"),
                "tipe_kendaraan": service.get("tipe_kendaraan"),
                "lc_per_hour": service.get("lc_per_hour"),
                "flat_rate": service.get("flat_rate")
            })
            
        return formatted_services

    except mysql.connector.Error as err:
        print(f"Services DB Error: {err}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error database: {err}")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
        
# --- Endpoint Sparepart Filtered (Perbaikan Logic) ---
@app.get("/api/spareparts/by-type")
async def get_spareparts_by_type(
    type: str = Query(..., description="Contoh input: Chery Omoda 5"), 
    current_user_phone: str = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    
    # CARA PANGGIL DI POSTMAN/BROWSER:
    # http://localhost:8000/api/spareparts/by-type?type=Chery Omoda 5
    
    conn = None
    cursor = None
    
    # Mapping nama mobil ke nama KOLOM di database
    # Pastikan nama kolom di database tidak mengandung spasi jika tidak pakai backticks, 
    # tapi di sini kita pakai backtick (`) jadi aman.
    column_key = None
    
    # Cek mapping
    for generic_name, specific_models in CAR_COLUMN_MAPPING.items():
        if type in specific_models:
            column_key = type
            break
        # Jika user mencari grup umum, misal "Chery Omoda 5", kita ambil salah satu varian default?
        # Atau biarkan dia mencari kolom dengan nama persis.
        if type == generic_name:
            # Opsional: Mapping generic name ke salah satu kolom default, misal Omoda 5 RZ
            # column_key = "Omoda 5 RZ" 
            pass

    # Jika tidak ada di mapping, gunakan input user (dengan resiko kolom tidak ada)
    if not column_key:
        column_key = type 

    # Sanitasi input dasar untuk mencegah SQL Injection via nama kolom (meski sulit di variable binding)
    # Kita hanya izinkan alphanumeric, spasi, dan strip/underscore
    import re
    if not re.match(r"^[a-zA-Z0-9 _-]+$", column_key):
        raise HTTPException(status_code=400, detail="Format tipe mobil tidak valid.")

    compatibility_column = f"`{column_key}`"

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True) 

        # Query: Ambil sparepart dimana kolom mobil tersebut bernilai 'ok' atau 'v'
        query = f"""
            SELECT 
                `nomor_sparepart` AS part_number,
                `nama_sparepart` AS part_name,
                `harga_jual_exc_tax` AS price_str
            FROM sparepart_data
            WHERE {compatibility_column} = 'ok' OR {compatibility_column} = 'v'
        """
        
        cursor.execute(query) 
        spareparts_from_db = cursor.fetchall()

        cleaned_spareparts = []
        for part in spareparts_from_db:
            cleaned_price = clean_price_string(part.get("price_str")) 
            cleaned_spareparts.append({
                "part_number": part.get("part_number", "").strip(), 
                "part_name": part.get("part_name", "").strip(),
                "price": cleaned_price
            })

        return cleaned_spareparts

    except mysql.connector.Error as err:
        print(f"Spareparts Filter Error: {err}")
        # Handle error jika kolom tidak ada (Error 1054: Unknown column)
        if err.errno == 1054:
             raise HTTPException(
                 status_code=404, 
                 detail=f"Tipe mobil '{column_key}' tidak ditemukan dalam database (Kolom tidak ada)."
             )
        raise HTTPException(status_code=500, detail="Terjadi kesalahan pada server.")
                    
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

# --- 1. Tambahkan Model Baru di bagian atas (dekat UserCreate) ---
# --- 1. Tambahkan Model Khusus untuk Input Jasa Baru ---
class ServiceCreate(BaseModel):
    jenis_pekerjaan: str
    lc_per_hour: float

# --- 2. Tambahkan Endpoint POST Baru ---
@app.post("/api/services/add", status_code=status.HTTP_201_CREATED)
async def add_custom_service(service: ServiceCreate, current_user_phone: str = Depends(get_current_user)):
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Generate Kode Unik Otomatis (misal: SVC-A1B2)
        unique_code = f"SVC-{str(uuid.uuid4())[:4].upper()}"

        # Simpan ke Database
        # Pastikan kolom hourly_rate sesuai dengan struktur tabel Anda
        cursor.execute(
            "INSERT INTO services_data (code, jenis_pekerjaan, lc_per_hour) VALUES (%s, %s, %s)",
            (unique_code, service.jenis_pekerjaan, service.lc_per_hour)
        )
        conn.commit()

        # Kembalikan data ke Frontend agar bisa langsung dipakai
        return {
            "code": unique_code,
            "jenis_pekerjaan": service.jenis_pekerjaan,
            "price": service.lc_per_hour
        }

    except mysql.connector.Error as err:
        print(f"Add Service Error: {err}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan jasa baru.")
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()


def format_whatsapp_id(phone: str) -> str:
    # ... (Logika konversi 08xxx/628xxx ke 628xxx@s.whatsapp.net) ...
    if not phone: return ""
    cleaned = ''.join(filter(str.isdigit, phone))
    if cleaned.startswith('0'): cleaned = '62' + cleaned[1:]
    elif not cleaned.startswith('62') and len(cleaned) >= 8: cleaned = '62' + cleaned
    return cleaned + '@s.whatsapp.net'


@app.post("/api/invoice/send_whatsapp")
async def send_invoice_handler(data: InvoicePayload):
    
    # [1] Validasi nomor WhatsApp
    target_phone_wa_id = format_whatsapp_id(data.customer.phone)
    if not target_phone_wa_id:
        raise HTTPException(status_code=400, detail="Nomor HP pelanggan tidak valid.")

    # [2] Buat PDF Invoice
    try:
        # --- PREPARE DATA FOR HTML GENERATOR ---
        invoice_number = f"INV-{int(time.time())}"
        invoice_date = datetime.now().strftime("%d %B %Y")
        
        # Generate Rows HTML
        item_rows_html = ""
        for item in data.items:
            item_total = 0
            price_display = ""
            qty_display = ""
            
            if item.type == 'service':
                # Logic: (Rate / 100) * Qty
                qty = item.quantity if item.quantity else 100
                item_total = (item.lc_per_hour / 100) * qty
                price_display = f"Rp {item.lc_per_hour:,.0f}/100m".replace(",", ".")
                qty_display = f"{qty/100} Jam"
            else:
                qty = item.quantity if item.quantity else 1
                item_total = item.price * qty
                price_display = f"Rp {item.price:,.0f}".replace(",", ".")
                qty_display = f"{qty} Pcs"
            
            total_display = f"Rp {item_total:,.0f}".replace(",", ".")
            
            item_rows_html += f"""
            <tr class="border-b border-gray-200">
                <td class="py-2">
                    <div class="font-medium text-gray-800">{item.name}</div>
                    <div class="text-xs text-gray-500">{item.code}</div>
                </td>
                <td class="py-2 text-xs">{item.type}</td>
                <td class="py-2 text-right text-xs">{price_display}</td>
                <td class="py-2 text-center text-xs">{qty_display}</td>
                <td class="py-2 text-right font-bold text-xs">{total_display}</td>
            </tr>
            """

        html_content = generate_invoice_html(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            customer=data.customer,
            item_rows=item_rows_html,
            subtotal=data.totals.get('subtotal', 0),
            discount=data.totals.get('discount', 0),
            ppn=data.totals.get('ppn', 0),
            grand_total=data.totals.get('grand_total', 0)
        )
        pdf_bytes = HTML(string=html_content).write_pdf()

        filename = f"invoice_{data.customer.phone}_{int(time.time())}.pdf"
        final_save_path = LOCAL_SAVE_DIR / filename
        final_save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(final_save_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"PDF Generated: {final_save_path}, Size: {len(pdf_bytes)} bytes") # Debug log

        public_pdf_url = f"{PUBLIC_BASE_URL}/{filename}"

    except Exception as e:
        print(f"PDF Handling Error: {e}")
        raise HTTPException(status_code=500, detail="Gagal membuat file PDF.")

    # ==================================================================
    # [3] WHATSAPP PAYLOAD — "ONE CONTENT TYPE ONLY"
    # ==================================================================
    target_phone_raw = format_whatsapp_id(data.customer.phone).split('@')[0] 
    public_pdf_url = f"{PUBLIC_BASE_URL}/{filename}"
    headers={"Content-Type": "application/json", "x-api-key": SENDABLE_API_KEY}

    payload = {
    "chatId": f"{target_phone_raw}@s.whatsapp.net",
    "document": {
        "url": public_pdf_url,
        "filename": f"Invoice_Estimasi_{target_phone_raw}.pdf",
        "caption": ""  # <-- WAJIB ADA MESKI KOSONG!!!
    }
}



    # Pastikan Anda menggunakan `json=payload` saat melakukan requests.post()
    try:
        response = requests.post(
            WHATSAPP_API_URL,
            headers={"Content-Type": "application/json", "x-api-key": SENDABLE_API_KEY},
            json=payload # PENTING
        )

    # Hapus potensi field lain yang menyebabkan error:
    # NO text, NO caption, NO body, NO image.
    # ==================================================================
        print("\n=== RESPONSE SENDABLE ===")
        print("Status:", response.status_code)
        print("Body:", response.text)
        print(public_pdf_url)

        response.raise_for_status()

        return {
            "message": "Invoice PDF berhasil dikirim ke WhatsApp!",
            "status": response.json()
        }

    except requests.exceptions.HTTPError as err:
        error_json = err.response.json()
        print("Sendable API Error:", error_json)
        raise HTTPException(status_code=500, detail=error_json.get("message"))



def format_rupiah(amount):
    """Fungsi untuk memformat angka menjadi string Rupiah (Rp 123.456)"""
    if amount is None or math.isnan(amount):
        amount = 0
    return f"Rp {amount:,.0f}".replace(",", "_").replace(".", ",").replace("_", ".")


def generate_invoice_html(invoice_number, invoice_date, customer, item_rows, subtotal, discount, ppn, grand_total):
    # Helper format rupiah (jika belum ada di kode utama Anda)
    def format_rupiah(value):
        return f"Rp {value:,.0f}".replace(",", ".")

    # CSS Replacement for Tailwind (WeasyPrint compatible)
    css_styles = """
        @page { size: A4; margin: 0; }
        *, ::before, ::after { box-sizing: border-box; }
        html { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px; color: #374151; }
        body { margin: 0; background-color: #fff; }
        
        /* Layout Utilities */
        .flex { display: flex; }
        .flex-row { flex-direction: row; }
        .flex-col { flex-direction: column; }
        .items-center { align-items: center; }
        .justify-between { justify-content: space-between; }
        .justify-center { justify-content: center; }
        .gap-3 { gap: 0.75rem; }
        .gap-4 { gap: 1rem; }
        .gap-6 { gap: 1.5rem; }
        .gap-8 { gap: 2rem; }
        
        /* Widths */
        .w-full { width: 100%; }
        .w-2-3 { width: 66.666667%; }
        .w-1-3 { width: 33.333333%; }
        .w-3-5 { width: 60%; }
        .w-2-5 { width: 40%; }
        .w-1-2 { width: 50%; }
        .w-5-12 { width: 41.666667%; }
        .w-2-12 { width: 16.666667%; }
        .w-1-12 { width: 8.333333%; }
        
        /* Spacing & Borders */
        .p-6 { padding: 1.5rem; }
        .p-4 { padding: 1rem; }
        .p-3 { padding: 0.75rem; }
        .p-2 { padding: 0.5rem; }
        .py-2 { padding-top: 0.5rem; padding-bottom: 0.5rem; }
        .px-6 { padding-left: 1.5rem; padding-right: 1.5rem; }
        .mb-1 { margin-bottom: 0.25rem; }
        .mb-2 { margin-bottom: 0.5rem; }
        .mb-3 { margin-bottom: 0.75rem; }
        .mb-4 { margin-bottom: 1rem; }
        .mt-0-5 { margin-top: 0.125rem; }
        
        .border { border: 1px solid #e5e7eb; }
        .border-b { border-bottom: 1px solid #e5e7eb; }
        .border-t { border-top: 1px solid #e5e7eb; }
        .border-l { border-left: 1px solid #e5e7eb; }
        .border-l-2 { border-left: 2px solid #4f46e5; }
        .border-gray-100 { border-color: #f3f4f6; }
        .border-gray-200 { border-color: #e5e7eb; }
        .rounded { border-radius: 0.25rem; }
        
        /* Typography */
        .text-xs { font-size: 0.75rem; line-height: 1rem; }
        .text-sm { font-size: 0.875rem; line-height: 1.25rem; }
        .text-base { font-size: 1rem; line-height: 1.5rem; }
        .text-lg { font-size: 1.125rem; line-height: 1.75rem; }
        .text-xl { font-size: 1.25rem; line-height: 1.75rem; }
        .text-2xl { font-size: 1.5rem; line-height: 2rem; }
        .font-bold { font-weight: 700; }
        .font-extrabold { font-weight: 800; }
        .font-medium { font-weight: 500; }
        .font-light { font-weight: 300; }
        .font-mono { font-family: monospace; }
        .uppercase { text-transform: uppercase; }
        .tracking-wider { letter-spacing: 0.05em; }
        .tracking-widest { letter-spacing: 0.1em; }
        .italic { font-style: italic; }
        .text-center { text-align: center; }
        .text-right { text-align: right; }
        
        /* Colors */
        .text-white { color: #ffffff; }
        .text-primary { color: #4f46e5; }
        .text-slate-400 { color: #94a3b8; }
        .text-slate-500 { color: #64748b; }
        .text-slate-600 { color: #475569; }
        .text-slate-700 { color: #334155; }
        .text-slate-800 { color: #1e293b; }
        .text-slate-900 { color: #0f172a; }
        .text-red-500 { color: #ef4444; }
        
        .bg-white { background-color: #ffffff; }
        .bg-primary { background-color: #4f46e5; }
        .bg-slate-50 { background-color: #f8fafc; }
        .bg-gray-50 { background-color: #f9fafb; }
        .bg-gray-100 { background-color: #f3f4f6; }
        .bg-slate-900 { background-color: #0f172a; }
        .bg-blue-600 { background-color: #2563eb; }
        
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; }
        .invoice-box { width: 100%; max-width: 210mm; margin: 0 auto; background: white; }
    """

    return f"""
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <title>Invoice {invoice_number}</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        {css_styles}
    </style>
</head>
<body>
    <div class="invoice-box">
        <!-- HEADER -->
        <div class="flex flex-row border-b border-gray-100">
            <!-- Left: Brand -->
            <div class="w-2-3 p-6 bg-white flex flex-col justify-center">
                <div class="flex items-center gap-3 mb-3">
                    <div class="w-8 h-8 bg-primary rounded flex items-center justify-center text-white text-base" style="width: 32px; height: 32px; display:flex; align-items:center; justify-content:center;">
                        <span style="font-size: 16px;">EP</span>
                    </div>
                    <div>
                        <h1 class="text-xl font-extrabold text-slate-900 tracking-tight" style="margin:0;">ENDLESS PROJECT</h1>
                        <p class="text-xs text-primary font-bold uppercase tracking-widest mt-0-5" style="font-size: 10px;">Automotive Solutions</p>
                    </div>
                </div>
                
                <div class="text-xs text-slate-500">
                    <p class="font-bold text-slate-700" style="margin:0;">Kantor Pusat & Workshop:</p>
                    <p style="margin:0;">Jl. Otomotif Raya No. 88, Kawasan Industri, Medan 20111</p>
                    <div class="flex gap-4 mt-1" style="font-size: 11px;">
                        <p style="margin:0;">support@endlessproject.com</p>
                        <p style="margin:0;">+62 812-3456-7890</p>
                    </div>
                </div>
            </div>

            <!-- Right: Invoice Meta -->
            <div class="w-1-3 bg-primary p-6 text-white flex flex-col justify-center">
                <h2 class="text-2xl font-light mb-3" style="opacity: 0.9; margin-top:0;">INVOICE</h2>
                
                <div class="text-sm">
                    <div class="mb-2">
                        <p class="text-xs uppercase" style="opacity: 0.7; font-weight: 600; margin:0;">Nomor Referensi</p>
                        <p class="text-base font-bold font-mono" style="margin:0;">{invoice_number}</p>
                    </div>
                    <div>
                        <p class="text-xs uppercase" style="opacity: 0.7; font-weight: 600; margin:0;">Tanggal Terbit</p>
                        <p class="font-medium text-sm" style="margin:0;">{invoice_date}</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- CUSTOMER & VEHICLE DETAILS -->
        <div class="p-6 border-b border-gray-100 bg-slate-50">
            <div class="flex flex-row gap-6">
                <!-- Bill To -->
                <div class="w-1-2">
                    <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Informasi Pelanggan</h3>
                    <div class="border-l-2" style="padding-left: 0.75rem;">
                        <p class="text-sm font-bold text-slate-800" style="margin:0;">{getattr(customer, 'name', '-')}</p>
                        <p class="text-xs text-slate-600 mt-0-5" style="margin:0;">{getattr(customer, 'phone', '-')}</p>
                        <p class="text-xs text-slate-400 mt-0-5" style="font-size: 10px; margin:0;">ID: {getattr(customer, 'id', 'CUST-REG-2024')}</p>
                    </div>
                </div>

                <!-- Vehicle Info -->
                <div class="w-1-2">
                    <h3 class="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Detail Kendaraan</h3>
                    <div class="bg-white rounded border border-gray-200 p-2 flex gap-3 items-center">
                        <div class="text-center" style="min-width: 80px;">
                            <span class="text-xs text-slate-500 block uppercase" style="font-size: 9px;">Plat Nomor</span>
                            <span class="text-xs font-bold font-mono text-slate-800 bg-gray-100 px-2 rounded block mt-0-5" style="padding-top:2px; padding-bottom:2px;">{getattr(customer, 'plate', '-')}</span>
                        </div>
                        <div class="border-l border-gray-100" style="padding-left: 0.75rem;">
                            <span class="text-xs text-slate-500 block uppercase" style="font-size: 9px;">Catatan</span>
                            <p class="text-xs text-slate-600 italic" style="margin:0;">{getattr(customer, 'note', '-')}</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- TABLE -->
        <div class="px-6 py-2" style="min-height: 150px;">
            <table class="w-full text-left">
                <thead>
                    <tr class="border-b border-gray-200">
                        <th class="py-2 text-xs font-bold text-primary uppercase tracking-wider w-5-12">Deskripsi Layanan</th>
                        <th class="py-2 text-xs font-bold text-primary uppercase tracking-wider w-2-12">Tipe</th>
                        <th class="py-2 text-xs font-bold text-primary uppercase tracking-wider w-2-12 text-right">Harga</th>
                        <th class="py-2 text-xs font-bold text-primary uppercase tracking-wider w-1-12 text-center">Qty</th>
                        <th class="py-2 text-xs font-bold text-primary uppercase tracking-wider w-2-12 text-right">Total</th>
                    </tr>
                </thead>
                <tbody class="text-xs text-slate-600">
                    {item_rows}
                </tbody>
            </table>
        </div>

        <!-- BOTTOM SECTION -->
        <div class="bg-gray-50 p-6 border-t border-gray-200">
            <div class="flex flex-row gap-8">
                
                <!-- Left: Info & Terms -->
                <div class="w-3-5">
                    <!-- Bank Info -->
                    <div class="flex items-center gap-3 bg-white border border-gray-200 p-3 rounded mb-4">
                        <div class="bg-blue-600 text-white font-bold text-xs px-2 rounded" style="padding-top:2px; padding-bottom:2px;">BCA</div>
                        <div>
                            <p class="text-xs font-bold text-slate-800" style="margin:0;">8820-1234-5678</p>
                            <p class="text-xs text-slate-500" style="font-size: 10px; margin:0;">a.n Endless Project Official</p>
                        </div>
                    </div>

                    <!-- Terms -->
                    <div>
                        <h4 class="text-xs font-bold text-slate-800 uppercase mb-1" style="font-size: 10px;">Ketentuan</h4>
                        <ul class="text-slate-500" style="font-size: 9px; padding-left: 1.5rem; margin:0;">
                            <li>Dokumen ini merupakan estimasi biaya, bukan bukti pembayaran lunas.</li>
                            <li>Harga suku cadang dapat berubah mengikuti harga pasar.</li>
                            <li>Garansi servis berlaku 7 hari setelah penyerahan.</li>
                        </ul>
                    </div>
                </div>

                <!-- Right: Totals -->
                <div class="w-2-5">
                    <div class="bg-white p-4 rounded border border-gray-100 mb-4">
                        <div class="flex justify-between items-center mb-1 text-xs">
                            <span class="text-slate-500">Subtotal</span>
                            <span class="font-bold text-slate-800">{format_rupiah(subtotal)}</span>
                        </div>
                        <div class="flex justify-between items-center mb-1 text-xs text-red-500">
                            <span>Diskon</span>
                            <span class="font-bold">- {format_rupiah(discount)}</span>
                        </div>
                        <div class="flex justify-between items-center mb-2 text-xs text-slate-500">
                            <span>PPN (11%)</span>
                            <span class="font-bold">{format_rupiah(ppn)}</span>
                        </div>
                        
                        <div class="border-t border-gray-200" style="margin: 0.5rem 0; border-style: dashed;"></div>
                        
                        <div class="flex justify-between items-center">
                            <span class="text-xs font-bold text-slate-900 uppercase">Total</span>
                            <span class="text-lg font-extrabold text-primary">{format_rupiah(grand_total)}</span>
                        </div>
                    </div>

                    <!-- Signature -->
                    <div class="text-center">
                        <p class="text-slate-400 mb-6" style="font-size: 10px;">Disetujui Oleh,</p>
                        <div class="border-t border-slate-300" style="width: 50%; margin: 0 auto; padding-top: 4px;">
                            <p class="font-bold text-slate-700" style="font-size: 10px;">Endless Management</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer -->
        <div class="bg-slate-900 text-slate-400 py-2 px-4 text-center" style="font-size: 9px;">
            <p style="margin:0;">&copy; 2024 Endless Project Automotive. All Rights Reserved.</p>
        </div>
    </div>
</body>
</html>
"""