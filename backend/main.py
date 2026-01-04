import os
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
from dotenv import load_dotenv
from pathlib import Path
import math
import time
import requests
import json
from fastapi import Request
from analisisdata import router as analisisdata_router # Import router dari analisisdata.py



SENDABLE_API_KEY = "send_ab562d228ad7c5890fba9681a9fd02dcaeb69f702d1bf5d758858f4ca804c990" 
WHATSAPP_API_URL = "https://api.sendable.dev/w/messages.send"
PUBLIC_BASE_URL = "https://endlessproject.my.id/api/invoices"
FRONTEND_BUILD_DIR = Path("./frontend-build")
LOCAL_SAVE_DIR = FRONTEND_BUILD_DIR / "invoices"
load_dotenv()

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
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "root") # Ingat ganti ini!
DATABASE_NAME = os.getenv("DATABASE_NAME", "chatbot_history")
# Pastikan JWT_SECRET kuat dan diambil dari environment variable di production!
JWT_SECRET = os.getenv("JWT_SECRET", "AD8622")
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
        password_byte_enc = plain_password.encode('utf-8')
        hashed_password_byte_enc = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)
    except ValueError: # bcrypt.checkpw dapat mengeluarkan ValueError untuk format hash yang tidak valid
        print("DEBUG: Format hash bcrypt yang disimpan tidak valid.")
        return False
    except Exception as e:
        print(f"DEBUG: Error tak terduga saat verifikasi password: {e}")
        return False

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
    index_path = FRONTEND_BUILD_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail=f"File frontend 'index.html' tidak ditemukan di path: {index_path.resolve()}")
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
        raise HTTPException(status_code=400, detail="Nomor sudah terdaftar")

    cursor.close()
    conn.close()

    # 4. KIRIM KE N8N (INI INTINYA 🔥)
    n8n_payload = {
        "phone_number": data.phone_number,
        "password": data.password,
        "ip": request.client.host,
        "user_agent": request.headers.get("user-agent")
    }

    n8n_response = requests.post(
        os.getenv("N8N_REGISTER_WEBHOOK"),
        json=n8n_payload,
        timeout=10
    )

    if n8n_response.status_code != 200:
        raise HTTPException(status_code=500, detail="Gagal mengirim ke sistem approval")

    # 5. RESPONSE KE FRONTEND
    return {
        "status": "pending",
        "message": "Permintaan pendaftaran dikirim. Menunggu persetujuan admin."
    }


class UserLogin(BaseModel):
    phone_number: str
    password: str
    captcha_token: str


@app.post("/api/login", response_model=Token)
async def login_for_access_token(user: UserLogin):

    # 1️⃣ VALIDASI CAPTCHA
    captcha_verify = requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={
            "secret": os.getenv("TURNSTILE_SECRET"),
            "response": user.captcha_token
        }
    ).json()

    if not captcha_verify.get("success"):
        raise HTTPException(status_code=400, detail="CAPTCHA tidak valid")

    # 2️⃣ CEK USER DI DATABASE
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT phone_number, password_hash FROM users WHERE phone_number = %s",
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
        "token_type": "bearer"
    }


# --- Sertakan Router Analisis Data ---
# Semua endpoint di analisisdata_router akan memerlukan otentikasi JWT
app.include_router(analisisdata_router, dependencies=[Depends(get_current_user)])

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
        cursor.execute("SELECT role FROM users WHERE phone_number = %s", (current_user_phone,))
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

        # Query untuk mengambil semua transaksi berdasarkan order yang dimiliki user
        # Ini adalah query yang cukup kompleks, menggabungkan data dari 'orders' dan 'payment_transactions'
        query = """
            SELECT DISTINCT pt.*
            FROM payment_transactions pt
            JOIN orders o ON FIND_IN_SET(o.id, pt.order_ids)
            WHERE o.user_phone_number = %s
            ORDER BY pt.created_at DESC;
        """
        cursor.execute(query, (current_user_phone,))
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
async def send_invoice_handler(data: InvoicePayload, current_user_phone: str = Depends(get_current_user)):
    
    # [1] Validasi nomor WhatsApp
    target_phone_wa_id = format_whatsapp_id(data.customer.phone)
    if not target_phone_wa_id:
        raise HTTPException(status_code=400, detail="Nomor HP pelanggan tidak valid.")

    # [2] Buat PDF Invoice
    try:
        html_content = generate_invoice_html(data)
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


def generate_invoice_html(data: InvoicePayload) -> str:
    """Merender data invoice dari Payload JSON menjadi dokumen HTML/PDF yang dicetak."""
    
    # Ambil data customer
    customer = data.customer
    
    # Ambil data total
    subtotal = data.totals.get('subtotal', 0)
    grand_total = data.totals.get('grand_total', 0)
    ppn = data.totals.get('ppn', 0)
    
    # Generate baris item
    item_rows = ""
    for item in data.items:
        # Kalkulasi total per item (LC/100 * Menit atau Price * Pcs)
        if item.type == 'service':
            item_total = (item.lc_per_hour / 100) * item.quantity
            unit_price_display = format_rupiah(item.lc_per_hour) + " /100 mnt"
            qty_display = f"{item.quantity / 100:.2f} Jam ({item.quantity} Menit)"
        else:
            item_total = item.price * item.quantity
            unit_price_display = format_rupiah(item.price) + " /pcs"
            qty_display = f"{item.quantity} Pcs"

        item_rows += f"""
        <tr>
            <td style="padding: 8px; border: 1px solid #ccc;">
                <div style="font-weight: bold;">{item.name}</div>
                <div style="font-size: 10px; color: #666;">Kode: {item.code}</div>
            </td>
            <td style="padding: 8px; border: 1px solid #ccc;">{data.car.get('model') or '-'}</td>
            <td style="padding: 8px; border: 1px solid #ccc; text-align: right; font-size: 12px;">{unit_price_display}</td>
            <td style="padding: 8px; border: 1px solid #ccc; text-align: center;">{qty_display}</td>
            <td style="padding: 8px; border: 1px solid #ccc; text-align: right; font-weight: bold;">{format_rupiah(item_total)}</td>
        </tr>
        """

    # --- HTML STRUCTURE ---
    return f"""
    <html>
    <head>
        <title>Invoice Estimasi</title>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: sans-serif; font-size: 12px; margin: 0; padding: 20px; color: #333; }}
            .container {{ width: 100%; max-width: 700px; margin: 0 auto; border: 1px solid #eee; padding: 20px; }}
            h1 {{ font-size: 20px; text-align: center; margin-bottom: 5px; color: #444; }}
            h3 {{ font-size: 14px; margin-bottom: 8px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
            .meta {{ text-align: center; margin-bottom: 20px; border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th {{ background-color: #f0f0f0; border: 1px solid #ccc; padding: 8px; text-align: left; }}
            td {{ border: 1px solid #ccc; padding: 8px; }}
            .totals-box {{ width: 250px; margin-left: auto; margin-top: 20px; }}
            .total-line {{ display: flex; justify-content: space-between; padding: 4px 0; }}
            .total-final {{ font-size: 14px; font-weight: bold; border-top: 2px solid #333; padding-top: 6px; color: #6a1b9a; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="meta">
                <h1>INVOICE ESTIMASI JASA</h1>
                <p>No. Invoice: INV-{datetime.now().strftime('%Y%m%d%H%M%S')}</p>
                <p>Tanggal: {datetime.now().strftime('%d %B %Y')}</p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <h3>Detail Pelanggan:</h3>
                <div style="line-height: 1.5;">
                    Nama: <strong>{customer.name or '-'}</strong> | 
                    Plat BK: <strong>{customer.plate or '-'}</strong> | 
                    No. HP: <strong>{customer.phone or '-'}</strong>
                    <br>Catatan: {customer.note or '-'}
                </div>
            </div>

            <div style="margin-bottom: 20px;">
                <h3>Detail Layanan:</h3>
                <table>
                    <thead>
                        <tr>
                            <th style="width: 40%;">Layanan</th>
                            <th style="width: 15%;">Model Mobil</th>
                            <th style="width: 20%; text-align: right;">Harga Satuan</th>
                            <th style="width: 10%; text-align: center;">Qty</th>
                            <th style="width: 15%; text-align: right;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>{item_rows}</tbody>
                </table>
            </div>

            <div class="totals-box">
                <div class="total-line"><span>Subtotal:</span> <span>{format_rupiah(subtotal)}</span></div>
                <div class="total-line"><span>Diskon:</span> <span>{format_rupiah(0)}</span></div>
                <div class="total-line"><span>PPN (11%):</span> <span>{format_rupiah(ppn)}</span></div>
                <div class="total-final total-line"><span>TOTAL:</span> <span>{format_rupiah(grand_total)}</span></div>
            </div>
        </div>
    </body>
    </html>
    """